from unittest.mock import MagicMock

from ollie_integrations_livekit.hooks import attach_ollie, get_last_wire_payload


def test_attach_ollie_without_livekit_does_not_raise():
    client = MagicMock()
    client.agent_id = "agent_test"
    attach_ollie(client, app_name="test_app")


def test_get_last_wire_payload_initially_none_or_dict():
    payload = get_last_wire_payload()
    assert payload is None or isinstance(payload, dict)
