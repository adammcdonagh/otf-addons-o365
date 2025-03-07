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

local_source_definition = {
    "directory": "",
    "filename": "",
    "protocol": {"name": "local"},
}

local_destination_definition = {
    "directory": "",
    "filename": "",
    "protocol": {"name": "local"},
}

sharepoint_destination_definition = {
    "siteHostname": None,
    "siteName": None,
    "directory": "dest",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
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

sharepoint_source_definition = {
    "siteHostname": None,
    "siteName": None,
    "directory": "src",
    "fileRegex": "^test.txt$",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
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

sharepoint_filewatch_task_definition_source = {
    "siteHostname": None,
    "siteName": None,
    "directory": "src",
    "fileRegex": ".*\\.txt",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
        "refreshToken": "",
        "clientId": None,
        "tenantId": None,
    },
    "fileWatch": {
        "timeout": 2,
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

sharepoint_destination_non_existent = {
    "siteHostname": None,
    "siteName": None,
    "directory": "dest/archive/anotherFolder/testFolder",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
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

sharepoint_source_definition_dest = {
    "siteHostname": None,
    "siteName": None,
    "directory": "dest",
    "fileRegex": "^pca_move_recursive.txt$",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
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


"""
These tests are hard to fully automate, given a full set of creds are needed for the environment.

The below tests assume the following exists in the Sharepoint site being tested against:

- A folder called "src" exists
- There are at least 2 files in the "src" folder
- At least one of the files is a .txt file
- There's a .txt file in the top level of the site (default Documents/Shared Documents list)

"""


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
        "sharepointSite": os.getenv("SHAREPOINT_SITE"),
        "sharepointHost": os.getenv("SHAREPOINT_HOST"),
        "refreshToken": os.getenv("REFRESH_TOKEN"),
        "rootDir": f"{current_dir}/../",
    }


def setup_creds_for_transfer(transfer_definition: dict, creds) -> dict:

    if (
        transfer_definition["source"]["protocol"]["name"]
        == "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer"
    ):

        transfer_definition["source"]["protocol"]["refreshToken"] = creds[
            "refreshToken"
        ]
        transfer_definition["source"]["protocol"]["tenantId"] = creds["tenantId"]
        transfer_definition["source"]["protocol"]["clientId"] = creds["clientId"]

        transfer_definition["source"]["siteHostname"] = creds["sharepointHost"]
        transfer_definition["source"]["siteName"] = creds["sharepointSite"]

        # Set cacheable variable to the right filename path
        transfer_definition["source"]["cacheableVariables"][0]["cacheArgs"][
            "file"
        ] = f"{creds['rootDir']}/refresh_token.txt"

    if (
        transfer_definition["destination"]
        and transfer_definition["destination"][0]["protocol"]["name"]
        == "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer"
    ):
        transfer_definition["destination"][0]["protocol"]["refreshToken"] = creds[
            "refreshToken"
        ]
        transfer_definition["destination"][0]["protocol"]["tenantId"] = creds[
            "tenantId"
        ]
        transfer_definition["destination"][0]["protocol"]["clientId"] = creds[
            "clientId"
        ]

        transfer_definition["destination"][0]["siteHostname"] = creds["sharepointHost"]
        transfer_definition["destination"][0]["siteName"] = creds["sharepointSite"]

        # Set cacheable variable to the right filename path
        transfer_definition["destination"][0]["cacheableVariables"][0]["cacheArgs"][
            "file"
        ] = f"{creds['rootDir']}/refresh_token.txt"

    return transfer_definition


def test_sharepoint_filewatch_root(tmpdir, o365_creds):

    # Load variables from the environment

    sharepoint_filewatch_task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_filewatch_task_definition_source),
        "destination": [deepcopy(local_destination_definition)],
    }

    sharepoint_filewatch_task_definition = setup_creds_for_transfer(
        sharepoint_filewatch_task_definition, o365_creds
    )

    # Set the directory to the top level
    sharepoint_filewatch_task_definition["source"]["directory"] = ""
    # Set the destination directory to the temp directory
    sharepoint_filewatch_task_definition["destination"][0]["directory"] = tmpdir.strpath

    transfer_obj = transfer.Transfer(
        None, "sharepoint_filewatch", sharepoint_filewatch_task_definition
    )

    assert transfer_obj.run()


def test_sharepoint_filewatch_sub_dir(tmpdir, o365_creds):

    # Load variables from the environment

    sharepoint_filewatch_task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_filewatch_task_definition_source),
        "destination": [deepcopy(local_destination_definition)],
    }

    sharepoint_filewatch_task_definition = setup_creds_for_transfer(
        sharepoint_filewatch_task_definition, o365_creds
    )

    # Set the directory to the src sub directory
    sharepoint_filewatch_task_definition["source"]["directory"] = "src"
    # Set the destination directory to the temp directory
    sharepoint_filewatch_task_definition["destination"][0]["directory"] = tmpdir.strpath

    transfer_obj = transfer.Transfer(
        None, "sharepoint_filewatch", sharepoint_filewatch_task_definition
    )

    assert transfer_obj.run()


def test_local_to_sharepoint_transfer(tmpdir, o365_creds):

    task_definition = {
        "type": "transfer",
        "source": deepcopy(local_source_definition),
        "destination": [deepcopy(sharepoint_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the directory to the temp directory
    task_definition["source"]["directory"] = tmpdir
    task_definition["source"]["fileRegex"] = "^test.txt$"

    # Create a file in the tmpdir
    with open(f"{tmpdir}/test.txt", "w") as f:
        f.write("test")

    transfer_obj = transfer.Transfer(None, "local-to-sharepoint-copy", task_definition)

    assert transfer_obj.run()


def test_sharepoint_pca_move_recursive(tmpdir, o365_creds):
    # Upload file first to ensure present before we move
    task_definition = {
        "type": "transfer",
        "source": deepcopy(local_source_definition),
        "destination": [deepcopy(sharepoint_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the directory to the temp directory
    task_definition["source"]["directory"] = tmpdir
    task_definition["source"]["fileRegex"] = "^pca_move_recursive2.txt$"
    task_definition["destination"][0]["directory"] = "dest"

    # Create a file in the tmpdir
    with open(f"{tmpdir}/pca_move_recursive2.txt", "w") as f:
        f.write("pca_move_recursive")

    transfer_obj = transfer.Transfer(None, "local-to-sharepoint-copy", task_definition)
    transfer_obj.run()

    # Then attempt transfer with sharepoint source with PCA move
    task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_source_definition_dest),
        "destination": [deepcopy(local_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the destination directory to the temp directory
    task_definition["destination"][0]["directory"] = tmpdir.strpath

    # Set the PCA with move
    task_definition["source"]["directory"] = "dest"
    task_definition["source"]["fileRegex"] = "^pca_move_recursive2.txt$"
    task_definition["source"]["postCopyAction"] = {
        "action": "move",
        "destination": "new_folder/another_folder/final_folder",
    }
    transfer_obj = transfer.Transfer(None, "sharepoint-to-local-copy", task_definition)

    assert transfer_obj.run()


def test_transfer_refresh_token_update(tmpdir, o365_creds):

    # Load variables from the environment

    task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_filewatch_task_definition_source),
        "destination": [deepcopy(local_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the destination directory to the temp directory
    task_definition["destination"][0]["directory"] = tmpdir.strpath

    transfer_obj = transfer.Transfer(None, "sharepoint_filewatch", task_definition)

    transfer_obj.run()

    # Check that the refresh_token.txt file has been updated and has something different
    # to before
    with open(f"{o365_creds['rootDir']}/refresh_token.txt", "r") as f:
        new_refresh_token = f.read()

    assert new_refresh_token != o365_creds["refreshToken"]


def test_sharepoint_to_local_transfer(tmpdir, o365_creds):

    task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_source_definition),
        "destination": [deepcopy(local_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the destination directory to the temp directory
    task_definition["destination"][0]["directory"] = tmpdir.strpath

    transfer_obj = transfer.Transfer(None, "sharepoint-to-local-copy", task_definition)

    assert transfer_obj.run()


def test_sharepoint_pca_delete(tmpdir, o365_creds):
    # Upload file first to ensure present before we delete
    task_definition = {
        "type": "transfer",
        "source": deepcopy(local_source_definition),
        "destination": [deepcopy(sharepoint_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the directory to the temp directory
    task_definition["source"]["directory"] = tmpdir
    task_definition["source"]["fileRegex"] = "^pca_delete.txt$"
    task_definition["destination"][0]["directory"] = "src/pca_delete"

    # Create a file in the tmpdir
    with open(f"{tmpdir}/pca_delete.txt", "w") as f:
        f.write("pca_delete")

    transfer_obj = transfer.Transfer(None, "local-to-sharepoint-copy", task_definition)
    transfer_obj.run()

    # Then attempt transfer with sharepoint source with PCA delete
    task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_source_definition),
        "destination": [deepcopy(local_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the destination directory to the temp directory
    task_definition["destination"][0]["directory"] = tmpdir.strpath

    # Set the PCA with delete
    task_definition["source"]["directory"] = "src/pca_delete"
    task_definition["source"]["fileRegex"] = "^pca_delete.txt$"
    task_definition["source"]["postCopyAction"] = {
        "action": "delete",
    }
    transfer_obj = transfer.Transfer(None, "sharepoint-to-local-copy", task_definition)

    assert transfer_obj.run()


def test_sharepoint_pca_move(tmpdir, o365_creds):
    # Upload file first to ensure present before we move
    task_definition = {
        "type": "transfer",
        "source": deepcopy(local_source_definition),
        "destination": [deepcopy(sharepoint_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the directory to the temp directory
    task_definition["source"]["directory"] = tmpdir
    task_definition["source"]["fileRegex"] = "^pca_move.txt$"
    task_definition["destination"][0]["directory"] = "src/pca_move"

    # Create a file in the tmpdir
    with open(f"{tmpdir}/pca_move.txt", "w") as f:
        f.write("pca_move")

    transfer_obj = transfer.Transfer(None, "local-to-sharepoint-copy", task_definition)
    transfer_obj.run()

    # Then attempt transfer with sharepoint source with PCA move
    task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_source_definition),
        "destination": [deepcopy(local_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the destination directory to the temp directory
    task_definition["destination"][0]["directory"] = tmpdir.strpath

    # Set the PCA with move
    task_definition["source"]["directory"] = "src/pca_move"
    task_definition["source"]["fileRegex"] = "^pca_move.txt$"
    task_definition["source"]["postCopyAction"] = {
        "action": "move",
        "destination": "archive2",
    }
    transfer_obj = transfer.Transfer(None, "sharepoint-to-local-copy", task_definition)

    assert transfer_obj.run()


def test_sharepoint_pca_rename(tmpdir, o365_creds):
    # Upload file first to ensure present before we rename
    task_definition = {
        "type": "transfer",
        "source": deepcopy(local_source_definition),
        "destination": [deepcopy(sharepoint_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the directory to the temp directory
    task_definition["source"]["directory"] = tmpdir
    task_definition["source"]["fileRegex"] = "^pca_rename.txt$"
    task_definition["destination"][0]["directory"] = "src/pca_rename"

    # Create a file in the tmpdir
    with open(f"{tmpdir}/pca_rename.txt", "w") as f:
        f.write("pca_rename")

    transfer_obj = transfer.Transfer(None, "local-to-sharepoint-copy", task_definition)
    transfer_obj.run()

    # Then attempt transfer with sharepoint source with PCA rename
    task_definition = {
        "type": "transfer",
        "source": deepcopy(sharepoint_source_definition),
        "destination": [deepcopy(local_destination_definition)],
    }

    task_definition = setup_creds_for_transfer(task_definition, o365_creds)

    # Set the destination directory to the temp directory
    task_definition["destination"][0]["directory"] = tmpdir.strpath

    # Set the PCA with rename
    task_definition["source"]["directory"] = "src/pca_rename"
    task_definition["source"]["fileRegex"] = "^pca_rename.txt$"
    task_definition["source"]["postCopyAction"] = {
        "action": "rename",
        "destination": "archive",
        "pattern": "rename",
        "sub": "renamed",
    }
    transfer_obj = transfer.Transfer(None, "sharepoint-to-local-copy", task_definition)

    assert transfer_obj.run()
