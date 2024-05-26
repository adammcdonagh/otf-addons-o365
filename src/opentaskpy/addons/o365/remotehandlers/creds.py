"""O365 helper functions."""

from msal import PublicClientApplication


def get_access_token(credentials: dict) -> dict:
    """Get an access token using the provided credentials.

    Args:
        credentials: The credentials to use
    """
    msal_app = PublicClientApplication(
        client_id=credentials["clientId"],
        authority=f"https://login.microsoftonline.com/{credentials['tenantId']}",
    )

    scopes = ["Sites.ReadWrite.All"]

    result = msal_app.acquire_token_by_refresh_token(
        credentials["refreshToken"], scopes
    )

    return {"access_token": result["access_token"], "expiry": "", "refresh_token": ""}
