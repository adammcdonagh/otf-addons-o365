# Changelog

## v26.10.1

- Add support for document libraries in Sharepoint
- Fixed post copy action renaming to overwrite existing files if they already exist

## v26.8.0

- Add conditionals property to sharepoint_source schema

## v26.6.0

- Add configurable timeout for large file uploads

## v25.34.0

- _Fix_ upload session logic to not exit after the first file

## v25.27.0

- Change file uploads > 200MB to use upload sessions.

## v25.9.0

- Add recursive folder creation in Sharepoint

## v24.44.0

- Add retry logic for 409 errors when uploading files to Sharepoint

## v24.30.0

- Add cacheableVariables to sharepoint source schema.

## v24.29.0

- Implement RemoteTransfer methods for sharepoint to act as a source, including PostCopyActions (move, delete, rename)

## v24.25.2

- Fix return code after successful upload

## v24.25.1

- Fix schemas

## v24.25.0

- Update build to include JSON schema files

## v24.23.0

- Initial version.
