"""O365 Sharepoint remote handler."""

import glob
import re
from datetime import datetime
from time import sleep

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

    def handle_post_copy_action(self, files: dict) -> int:
        """Handle the post copy action specified in the config.

        Args:
            files (dict): A list of files that need to be handled.

        Returns:
            int: 0 if successful, 1 if not.
        """
        # Check that our creds are valid
        self.validate_or_refresh_creds()

        # Determine the action to take
        # Delete the files
        if self.spec["postCopyAction"]["action"] == "delete":
            self.logger.info(f"Deleting files: {files}")
            # No way to bulk delete items from Sharepoint (it seems), so remove each individually
            for file_name, attributes in files.items():
                # Build up file path below site root
                file_path = f"{attributes['directory']}/{file_name}"
                # Get the file id and delete
                file_id = self.get_file_id_from_path(file_path)
                delete_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/items/{file_id}"
                response = requests.delete(
                    delete_url,
                    headers={
                        "Authorization": "Bearer " + self.credentials["access_token"],
                    },
                    timeout=60,
                )
                if response.status_code != 204:
                    self.logger.error(f"Failed to delete file: {file_name}")
                    self.logger.error(f"Got return code: {response.status_code}")
                    self.logger.error(response.json())
                    return 1
        # Copy the files to the new location, and then delete the originals
        if (
            self.spec["postCopyAction"]["action"] == "move"
            or self.spec["postCopyAction"]["action"] == "rename"
        ):
            for file_name, attributes in files.items():
                # Build up file path below site root
                file_path = f"{attributes['directory']}/{file_name}"
                file_id = self.get_file_id_from_path(file_path)
                new_file = f"{file_name.split('/')[-1]}"
                # Fetch id of new parent item from spec destination field
                destination_id = self.get_file_id_from_path(
                    self.spec["postCopyAction"]["destination"]
                )
                # Determine if we are renaming file
                if self.spec["postCopyAction"]["action"] == "rename":
                    # Use the pattern and sub values to rename the file correctly
                    new_file = re.sub(
                        self.spec["postCopyAction"]["pattern"],
                        self.spec["postCopyAction"]["sub"],
                        file_name,
                    )
                update_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/items/{file_id}"
                response = requests.patch(
                    update_url,
                    headers={
                        "Authorization": "Bearer " + self.credentials["access_token"],
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                    json={
                        "parentReference": {"id": f"{destination_id}"},
                        "name": f"{new_file}",
                    },
                )
                if response.status_code != 200:
                    self.logger.error(f"Failed to move file: {file_name}")
                    self.logger.error(f"Got return code: {response.status_code}")
                    self.logger.error(response.json())
                    return 1
        return 0

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
                            "directory": directory,
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
                max_retries = 5
                retry_delay = 1

                for attempt in range(max_retries):
                    response = requests.put(
                        upload_url,
                        headers={
                            "Authorization": "Bearer "
                            + self.credentials["access_token"],
                            "Content-Type": "application/json",
                        },
                        data=f,
                        timeout=60,
                    )
                    if response.status_code != 409:
                        break
                    if attempt < max_retries - 1:
                        sleep_time = retry_delay * (2**attempt)
                        self.logger.info(
                            f"Got 409 error from API. Sleeping for {sleep_time} seconds before retrying. Attempt {attempt} of {max_retries}"
                        )
                        sleep(sleep_time)
                else:
                    self.logger.error(
                        f"Failed to upload file after {max_retries} attempts due to 409 error"
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

    def pull_files_to_worker(self, files: dict, local_staging_directory: str) -> int:
        """Pull files to the worker.

        Download files from Sharepoint to the local staging directory.

        Args:
            files (list): A list of files to download.
            local_staging_directory (str): The local staging directory to download the
            files to.

        Returns:
            int: 0 if successful, 1 if not.
        """
        # Check that our creds are valid
        self.validate_or_refresh_creds()

        result = 0
        for file_name, attributes in files.items():
            # Build up file path below site root
            file_path = f"{attributes['directory']}/{file_name}"

            try:
                # Get the item id based on source path
                file_id = self.get_file_id_from_path(file_path)
                # Download file using item id
                self.logger.info(f"Downloading file: {file_name}")
                download_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/items/{file_id}/content"
                response = requests.get(
                    download_url,
                    headers={
                        "Authorization": "Bearer " + self.credentials["access_token"],
                    },
                    timeout=60,
                )

                # Check the response was a success
                if response.status_code not in (200, 201):
                    self.logger.error(f"Failed to download file: {file_name}")
                    self.logger.error(f"Got return code: {response.status_code}")
                    self.logger.error(response.json())
                    result = 1
                else:
                    local_file_name = f"{local_staging_directory}/{file_name}"
                    with open(local_file_name, "wb") as local_file:
                        local_file.write(response.content)
                    self.logger.info("Successfully downloaded file")
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.error(f"Failed to transfer file: {file_name}")
                self.logger.exception(e)
                result = 1

        return result

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

    def get_file_id_from_path(self, file_path: str) -> str:
        """Returns the id for a sharepoint drive item from the path."""
        item_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/root:/{file_path}"
        response = requests.get(
            item_url,
            headers={
                "Authorization": "Bearer " + self.credentials["access_token"],
            },
            timeout=60,
        )
        # Check the response was a success
        if response.status_code != 200:
            self.logger.error(f"Failed to get id for item with path: {file_path}")
            self.logger.error(f"Got return code: {response.status_code}")
            self.logger.error(response.json())
            raise RemoteTransferError(
                f"Failed to get id for item with path: {file_path}"
            )

        if response.json()["id"]:
            self.logger.info(f"Successfully fetched id for item with path: {file_path}")
            return str(response.json()["id"])

        raise RemoteTransferError(f"Failed to get id for item with path: {file_path}")
