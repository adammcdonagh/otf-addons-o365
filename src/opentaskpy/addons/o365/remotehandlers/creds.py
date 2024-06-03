"""O365 helper functions."""

from time import time

import opentaskpy.otflogging
from msal import PublicClientApplication
from opentaskpy.exceptions import RemoteTransferError


def get_access_token(credentials: dict) -> dict:
    """Get an access token using the provided credentials.

    Args:
        credentials: The credentials to use
    """
    msal_app = PublicClientApplication(
        client_id=credentials["clientId"],
        authority=f"https://login.microsoftonline.com/{credentials['tenantId']}",
    )

    logger = opentaskpy.otflogging.init_logging(__name__, None, None)

    scopes = ["Sites.ReadWrite.All"]

    # Check for a refresh token. If one is not present, then we need to get one,
    # which requires going through a different flow with msal and prompting for the
    # device login flow.

    result = None
    if credentials["refreshToken"]:
        result = msal_app.acquire_token_by_refresh_token(
            credentials["refreshToken"], scopes
        )
    else:
        flow = msal_app.initiate_device_flow(scopes)
        logger.info(flow["message"])

        result = msal_app.acquire_token_by_device_flow(flow)

    if not result or "error" in result:
        raise RemoteTransferError(
            f"Could not acquire token: {result.get('error_description')}"
        )

    # Get the current epoch
    expiry = int(time()) + result["expires_in"]

    return {
        "access_token": result["access_token"],
        "expiry": expiry,
        "refresh_token": result["refresh_token"],
    }
