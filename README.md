[![PyPi](https://img.shields.io/pypi/v/otf-addons-aws.svg)](https://pypi.org/project/otf-addons-aws/)
![unittest status](https://github.com/adammcdonagh/otf-addons-aws/actions/workflows/lint.yml/badge.svg)
[![Coverage](https://img.shields.io/codecov/c/github/adammcdonagh/otf-addons-aws.svg)](https://codecov.io/gh/adammcdonagh/otf-addons-aws)
[![License](https://img.shields.io/github/license/adammcdonagh/otf-addons-aws.svg)](https://github.com/adammcdonagh/otf-addons-aws/blob/master/LICENSE)
[![Issues](https://img.shields.io/github/issues/adammcdonagh/otf-addons-aws.svg)](https://github.com/adammcdonagh/otf-addons-aws/issues)
[![Stars](https://img.shields.io/github/stars/adammcdonagh/otf-addons-aws.svg)](https://github.com/adammcdonagh/otf-addons-aws/stargazers)

This repository contains addons to allow integration with MS Sharepoint via [Open Task Framework (OTF)](https://github.com/adammcdonagh/open-task-framework)

Open Task Framework (OTF) is a Python based framework to make it easy to run predefined file transfers and scripts/commands on remote machines.

This addons allows filewatches and pushes of files to Sharepoint Sites.

# O365 Credentials

This package uses `msal` to get OAuth2.0 creds for the MS Graph API. This includes `access_token` and `refresh_token`.

For tests to work, a `.env` file containing the following needs to be created at the root of this repo containing the following:

```
SHAREPOINT_HOST=
SHAREPOINT_SITE=
CLIENT_ID=
TENANT_ID=
```

An Enterprise Application needs to be configured within EntraID to allow the app to access the Sharepoint API using delegated permissions. These should be set up as follows:

![App Registration](image/app-reg.png)

Under Authentication, the following needs to be enabled:

![Auth](image/auth.png)

Once your app is set up, copy the "Application (client) ID" and "Directory (tenant) ID" into the `.env` file. The `SHAREPOINT_HOST` should be the hostname of your sharepoint instance , and the `SHAREPOINT_SITE` should be name of the Sharepoint site itself.

You will need a "service account" user to authenticate with. This user should have access to the Sharepoint site you want to interact with, and OTF will act on behalf of this user for any interactions with Sharepoint. Any files created will be owned by this user.

Once this is done, you can trigger OTF to perform a task, or run the test under `tests`. The test will cache a `refresh_token.txt` locally, after going through the login flow.

You will see a message in the logs stating that you need to log into your account in a web browser, along with a code to enter. Follow the instructions (logging in with your service account) to complete the process flow and get the credentials.

When using in a real environment, you'll want to make use of cacheable variables to ensure that the `refresh_token` is updated after each login. See the `test_taskhandler_transfer_sharepoint.py` file for an example of how this is done. The task definition in your `.json.j2` task definition will need to use the equivalent lookup plugin to obtain the `refresh_token` from the cache on startup.

# Transfers

Transfers require a few additional arguments to normal. These are:

- siteHostname: The hostname of the Sharepoint site
- siteName: The name of the Sharepoint site

As part of the upload, the `bucket-owner-full-control` ACL flag is applied to all files. This can be disabled by setting `disableBucketOwnerControlACL` to `true` in the `protocol` definition

### Supported features

- Plain file watch
- File watch/transfer with file size and age constraints

# Configuration

JSON configs for transfers can be defined as follows:

## Example File Watch Only

```json
"source": {
        "siteHostname": "mydomain.sharepoint.com",
        "siteName": "mysitename",
        "directory": "src",
        "fileRegex": ".*\\.txt",
        "protocol": {
            "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
            "refreshToken": "{{ SOME LOOKUP DEFINITION }}",
            "clientId": "my-application-id",
            "tenantId": "my-tenant-id"
        },
        "fileWatch": {
            "timeout": 2
        },
        "cacheableVariables": [
            {
                "variableName": "protocol.refreshToken",
                "cachingPlugin": "file",
                "cacheArgs": {
                    "file": "some-file.txt"
                }
            }
        ]
    }
```

## Example file upload

```json
"source": {
    "siteHostname": "mydomain.sharepoint.com",
        "siteName": "mysitename",
    "directory": "dest",
    "protocol": {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
        "refreshToken": "{{ SOME LOOKUP DEFINITION }}",
        "clientId": "my-application-id",
        "tenantId": "my-tenant-id"
    },
    "cacheableVariables": [
        {
            "variableName": "protocol.refreshToken",
            "cachingPlugin": "file",
            "cacheArgs": {
                "file": "some-file.txt",
            },
        }
    ],
}
```
