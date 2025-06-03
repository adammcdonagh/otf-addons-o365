"""O365 Email remote handler."""

from datetime import datetime

import opentaskpy.otflogging
import requests
from dateutil.tz import tzlocal
from opentaskpy.config.variablecaching import cache_utils
from opentaskpy.exceptions import RemoteTransferError
from opentaskpy.remotehandlers.remotehandler import RemoteTransferHandler

from .creds import get_access_token

MAX_FILES_PER_QUERY = 100


class EmailTransfer(RemoteTransferHandler):
    """Email remote transfer handler."""

    TASK_TYPE = "T"

    def __init__(self, spec: dict):
        """Initialise the EmailTransfer handler.

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
        url = f"https://graph.microsoft.com/v1.0/users/{self.spec['sourceEmailAddress']}/mailFolders/inbox/messages?$top=3"
        response = requests.get(
            url,
            headers=self.headers,
            timeout=5,
        ).json()

        # Check the response is OK
        if response.get("error"):
            self.logger.error(
                f"Error listing emails from Graph API: {response.get('error')}"
            )
            raise RemoteTransferError(response["error"]["message"])

        messages = response.get("value", [])
        # print("Adam's last 3 emails: ")
        for msg in messages:
            self.logger.info("subject: ", msg["subject"])

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
        """Not implemented for this handler."""
        raise NotImplementedError

    def move_files_to_final_location(self, files: list[str]) -> None:
        """Not implemented for this handler."""
        raise NotImplementedError

    def list_files(
        self, directory: str | None = None, file_pattern: str | None = None
    ) -> dict:
        """Not implemented for this handler."""
        raise NotImplementedError

    def pull_files(self, files: list[str]) -> None:
        """Not implemented for this handler."""
        raise NotImplementedError

    def push_files_from_worker(
        self, local_staging_directory: str, file_list: dict | None = None
    ) -> int:
        """Not implemented for this handler."""
        raise NotImplementedError

    def pull_files_to_worker(self, files: dict, local_staging_directory: str) -> int:
        """Not implemented for this handler."""
        raise NotImplementedError

    def transfer_files(
        self,
        files: list[str],
        remote_spec: dict,
        dest_remote_handler: RemoteTransferHandler,
    ) -> int:
        """Not implemented for this transfer type."""
        raise NotImplementedError
