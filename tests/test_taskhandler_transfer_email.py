# pylint: skip-file
# ruff: noqa
# mypy: ignore-errors
import os
from copy import deepcopy

import pytest
from dotenv import load_dotenv
from opentaskpy.taskhandlers import transfer

# Set the log level to maximum
os.environ["OTF_LOG_LEVEL"] = "DEBUG"

email_source_definition = {
    "sourceEmailAddress": "mcdonagha@365dev.alltlab.com",
    "emailSubject": "subject",
    "sender": "example@example.com",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.email.EmailTransfer",
        "refreshToken": "",
        "clientId": None,
        "tenantId": None,
    },
    "cacheableVariables": [
        {
            "variableName": "protocol.refreshToken",
            "cachingPlugin": "file",
            "cacheArgs": {
                "file": None,
            },
        }
    ],
}


local_destination_definition = {
    "directory": "",
    "filename": "",
    "protocol": {"name": "local"},
}


@pytest.fixture(scope="session")
def o365_creds():
    # If this is not github actions, then load variables from a .env file at the root of
    # the repo
    if "GITHUB_ACTIONS" not in os.environ:
        # Load contents of .env into environment
        # Get the current directory
        current_dir = os.path.dirname(os.path.realpath(__file__))
        load_dotenv(dotenv_path=f"{current_dir}/../.env")

    # If a refresh_token.txt exists at the root, then load that too
    if os.path.exists(f"{current_dir}/../refresh_token.txt"):
        with open(f"{current_dir}/../refresh_token.txt", "r") as f:
            os.environ["REFRESH_TOKEN"] = f.read()

    return {
        "clientId": os.getenv("CLIENT_ID"),
        "tenantId": os.getenv("TENANT_ID"),
        "refreshToken": os.getenv("REFRESH_TOKEN"),
        "rootDir": f"{current_dir}/../",
    }


def setup_creds_for_transfer(transfer_definition: dict, creds) -> dict:
    if (
        transfer_definition["source"]["protocol"]["name"]
        == "opentaskpy.addons.o365.remotehandlers.email.EmailTransfer"
    ):
        transfer_definition["source"]["protocol"]["refreshToken"] = creds[
            "refreshToken"
        ]
        transfer_definition["source"]["protocol"]["tenantId"] = creds["tenantId"]
        transfer_definition["source"]["protocol"]["clientId"] = creds["clientId"]

        # Set cacheable variable to the right filename path
        transfer_definition["source"]["cacheableVariables"][0]["cacheArgs"][
            "file"
        ] = f"{creds['rootDir']}/refresh_token.txt"

    return transfer_definition


def test_get_email_list(o365_creds):
    task_definition = {
        "type": "transfer",
        "source": deepcopy(email_source_definition),
        "destination": "",
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    transfer_obj = transfer.Transfer(None, "read-email-list", task_definition)

    assert transfer_obj.run()
