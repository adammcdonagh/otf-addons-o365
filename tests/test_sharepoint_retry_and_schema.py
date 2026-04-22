import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import requests
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from opentaskpy.addons.o365.remotehandlers.sharepoint import SharepointTransfer


@pytest.fixture
def sharepoint_transfer_obj() -> SharepointTransfer:
    """Build a SharepointTransfer object without running network-heavy __init__."""
    obj = SharepointTransfer.__new__(SharepointTransfer)
    obj.logger = MagicMock()
    return obj


def test_request_get_retries_on_read_timeout_and_logs(
    sharepoint_transfer_obj: SharepointTransfer,
) -> None:
    response = MagicMock()
    response.status_code = 200

    with patch(
        "opentaskpy.addons.o365.remotehandlers.sharepoint.requests.get",
        side_effect=[requests.exceptions.ReadTimeout("timeout"), response],
    ) as mock_get:
        result = sharepoint_transfer_obj._request(
            "GET", "https://example.com/resource", timeout=1
        )

    assert result is response
    assert mock_get.call_count == 2
    assert sharepoint_transfer_obj.logger.warning.called

    warning_call = sharepoint_transfer_obj.logger.warning.call_args
    assert warning_call.args[0].startswith("Retrying SharePoint request")
    assert warning_call.args[1] == "GET"
    assert warning_call.args[2] == "https://example.com/resource"


def test_request_post_dispatches_to_requests_post(
    sharepoint_transfer_obj: SharepointTransfer,
) -> None:
    response = MagicMock()
    response.status_code = 201

    with patch(
        "opentaskpy.addons.o365.remotehandlers.sharepoint.requests.post",
        return_value=response,
    ) as mock_post:
        result = sharepoint_transfer_obj._request(
            "POST", "https://example.com/resource", json={"name": "folder"}
        )

    assert result is response
    mock_post.assert_called_once()


def test_request_unsupported_method_raises_value_error(
    sharepoint_transfer_obj: SharepointTransfer,
) -> None:
    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        sharepoint_transfer_obj._request("PUT", "https://example.com/resource")


def _load_sharepoint_destination_protocol_schema() -> dict:
    schema_path = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "opentaskpy"
        / "addons"
        / "o365"
        / "remotehandlers"
        / "schemas"
        / "transfer"
        / "sharepoint_destination"
        / "protocol.json"
    )
    loaded = json.loads(schema_path.read_text(encoding="utf-8"))
    return cast(dict[Any, Any], loaded)


def _valid_protocol_payload() -> dict:
    return {
        "name": "opentaskpy.addons.o365.remotehandlers.sharepoint.SharepointTransfer",
        "refreshToken": "token",
        "clientId": "client-id",
        "tenantId": "tenant-id",
    }


def test_sharepoint_destination_protocol_timeout_is_optional() -> None:
    schema = _load_sharepoint_destination_protocol_schema()
    payload = _valid_protocol_payload()

    validate(instance=payload, schema=schema)


def test_sharepoint_destination_protocol_timeout_accepts_integer() -> None:
    schema = _load_sharepoint_destination_protocol_schema()
    payload = _valid_protocol_payload()
    payload["timeout"] = 45

    validate(instance=payload, schema=schema)


@pytest.mark.parametrize("bad_timeout", ["45", 4.5, True, None])
def test_sharepoint_destination_protocol_timeout_rejects_non_integer(
    bad_timeout: object,
) -> None:
    schema = _load_sharepoint_destination_protocol_schema()
    payload = _valid_protocol_payload()
    payload["timeout"] = bad_timeout

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)
