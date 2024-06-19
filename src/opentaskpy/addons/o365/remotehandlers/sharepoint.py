"""O365 Sharepoint remote handler."""

import glob
import re
from datetime import datetime

import opentaskpy.otflogging
import requests
from dateutil.tz import tzlocal
from opentaskpy.config.variablecaching import cache_utils
from opentaskpy.exceptions import RemoteTransferError
from opentaskpy.remotehandlers.remotehandler import RemoteTransferHandler

from .creds import get_access_token

MAX_FILES_PER_QUERY = 100


class SharepointTransfer(RemoteTransferHandler):
    """Sharepoint remote transfer handler."""

    TASK_TYPE = "T"

    def __init__(self, spec: dict):
        """Initialise the SharepointTransfer handler.

        Args:
            spec (dict): The spec for the transfer. This is either the source, or the
            destination spec.
        """
        self.logger = opentaskpy.otflogging.init_logging(
            __name__, spec["task_id"], self.TASK_TYPE
        )

        super().__init__(spec)

        self.credentials = get_access_token(self.spec["protocol"])
        # Update the refresh token in the spec
        self.spec["protocol"]["refreshToken"] = self.credentials["refresh_token"]

        self.validate_or_refresh_creds()

        if "cacheableVariables" in self.spec:
            self.handle_cacheable_variables()

        # Obtain the source site ID via the Graph API based on the site name and
        # hostname
        self.headers = {
            "Authorization": "Bearer " + self.credentials["access_token"],
            "Content-Type": "application/json",
        }
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{self.spec['siteHostname']}:/sites/{self.spec['siteName']}",
            headers=self.headers,
            timeout=5,
        ).json()

        # Check the response is OK
        if response.get("error"):
            self.logger.error(
                f"Error obtaining site ID from Graph API: {response.get('error')}"
            )
            raise RemoteTransferError(response["error"]["message"])
        self.site_id = response["id"]

    def validate_or_refresh_creds(self) -> None:
        """Check the expiry of the access token, and get a new one if necessary."""
        # Convert the epoch from the credentials into the current datatime
        expiry_datetime = datetime.fromtimestamp(
            self.credentials["expiry"], tz=tzlocal()
        )
        self.logger.debug(
            f"Creds expire at: {expiry_datetime} - Now: {datetime.now(tz=tzlocal())}"
        )

        # If the expiry time is less than the current time, refresh the creds
        if expiry_datetime < datetime.now(tz=tzlocal()):
            self.logger.info("Refreshing credentials")
            self.credentials = get_access_token(self.spec["protocol"])
            # Update the refresh token in the spec
            self.spec["protocol"]["refreshToken"] = self.credentials["refresh_token"]

        # If there's cacheable variables, handle them
        if "cacheableVariables" in self.spec:
            self.handle_cacheable_variables()

        return

    def handle_cacheable_variables(self) -> None:
        """Handle the cacheable variables."""
        # Obtain the "updated" value from the spec
        for cacheable_variable in self.spec["cacheableVariables"]:

            updated_value = self.obtain_variable_from_spec(
                cacheable_variable["variableName"], self.spec
            )

            cache_utils.update_cache(cacheable_variable, updated_value)

    def supports_direct_transfer(self) -> bool:
        """Return False, as all files should go via the worker."""
        return False

    def handle_post_copy_action(self, files: list[str]) -> int:
        """Handle the post copy action specified in the config.

        Args:
            files (list[str]): A list of files that need to be handled.

        Returns:
            int: 0 if successful, 1 if not.
        """
        raise NotImplementedError

    def list_files(
        self, directory: str | None = None, file_pattern: str | None = None
    ) -> dict:
        """Return list of files that match the source definition.

        Args:
            directory (str, optional): The directory to search in. Defaults to None.
            file_pattern (str, optional): The file pattern to search for. Defaults to
            None.

        Returns:
            dict: A dict of files that match the source definition.
        """
        remote_files = {}

        self.logger.info(
            f"Listing files in site {self.spec['siteName']} matching"
            f" {file_pattern} in {directory if directory else '/'}"
        )

        try:  # pylint: disable=too-many-nested-blocks

            # Build the path, depending if the directory is just "/" or "" or has a full path
            path = ""
            if (directory and directory == "/") or not directory:
                path = "root/children"
            elif directory:
                path = f"root:/{directory}:/children"

            url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/{path}"

            while True:
                # Check that our creds are valid
                self.validate_or_refresh_creds()
                headers = {
                    "Authorization": "Bearer " + self.credentials["access_token"],
                    "Content-Type": "application/json",
                }

                response = requests.get(
                    url,
                    headers=headers,
                    timeout=30,
                ).json()

                if "value" in response and response["value"]:
                    for object_ in response["value"]:
                        file_name = object_["name"]

                        if file_pattern and not re.match(file_pattern, file_name):
                            continue

                        # Check that this is a file, and not a directory
                        if object_.get("folder"):
                            continue

                        self.logger.info(f"Found file: {file_name}")

                        # Get the size and modified time
                        last_modified = datetime.strptime(
                            object_["lastModifiedDateTime"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                        size = object_["size"]

                        remote_files[file_name] = {
                            "size": size,
                            "modified_time": last_modified.timestamp(),
                        }
                else:
                    break

                if response.get("@odata.nextLink"):
                    url = response["@odata.nextLink"]
                else:
                    break

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error(f"Error listing files in site: {self.spec['siteName']}")
            self.logger.exception(e)
            raise e

        return remote_files

    def move_files_to_final_location(self, files: list[str]) -> None:
        """Not implemented for this handler."""
        raise NotImplementedError

    # When Sharepoint is the destination
    def pull_files(self, files: list[str]) -> None:
        """Not implemented for this handler."""
        raise NotImplementedError

    def push_files_from_worker(
        self, local_staging_directory: str, file_list: dict | None = None
    ) -> int:
        """Push files from the worker to the destination server.

        Args:
            local_staging_directory (str): The local staging directory to upload the
            files from.
            file_list (dict, optional): The list of files to transfer. Defaults to None.

        Returns:
            int: 0 if successful, 1 if not.
        """
        # Check that our creds are valid
        self.validate_or_refresh_creds()

        result = 0

        if file_list:
            files = list(file_list.keys())
        else:
            files = glob.glob(f"{local_staging_directory}/*")

        for file in files:
            # Strip the directory from the file
            file_name = file.split("/")[-1]
            # Handle any rename that might be specified in the spec
            if "rename" in self.spec:
                rename_regex = self.spec["rename"]["pattern"]
                rename_sub = self.spec["rename"]["sub"]

                file_name = re.sub(rename_regex, rename_sub, file_name)
                self.logger.info(f"Renaming file to {file_name}")

            # Append a directory if one is defined
            if "directory" in self.spec:
                file_name = f"{self.spec['directory']}/{file_name}"

            self.logger.info(
                f"Uploading file: {file} to site {self.spec['siteName']} with path: {file_name}"
            )

            upload_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/root:/{file_name}:/content"
            with open(file, "rb") as f:
                response = requests.put(
                    upload_url,
                    headers={
                        "Authorization": "Bearer " + self.credentials["access_token"],
                        "Content-Type": "application/json",
                    },
                    data=f,
                    timeout=60,
                )

                # Check the response was a success
                if response.status_code not in (200, 201):
                    self.logger.error(f"Failed to upload file: {file}")
                    self.logger.error(f"Got return code: {response.status_code}")
                    self.logger.error(response.json())
                    result = 1
                else:
                    self.logger.info(
                        f"Successfully uploaded file to: {response.json()['webUrl']}"
                    )

        return result

    def pull_files_to_worker(
        self, files: list[str], local_staging_directory: str
    ) -> int:
        """Pull files to the worker.

        Download files from Sharepoint to the local staging directory.

        Args:
            files (list): A list of files to download.
            local_staging_directory (str): The local staging directory to download the
            files to.

        Returns:
            int: 0 if successful, 1 if not.
        """
        raise NotImplementedError

    def transfer_files(
        self,
        files: list[str],
        remote_spec: dict,
        dest_remote_handler: RemoteTransferHandler,
    ) -> int:
        """Not implemented for this transfer type."""
        raise NotImplementedError

    def create_flag_files(self) -> int:
        """Not implemented for this transfer type."""
        raise NotImplementedError

    def tidy(self) -> None:
        """Nothing to tidy."""
