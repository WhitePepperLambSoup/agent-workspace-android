"""Bounded NDJSON gateway used by the Electron desktop shell."""

from agent_workspace.ui_gateway.protocol import (
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    CommandEnvelope,
    ProtocolError,
    encode_message,
    parse_command_line,
)

__all__ = [
    "MAX_MESSAGE_BYTES",
    "PROTOCOL_VERSION",
    "CommandEnvelope",
    "ProtocolError",
    "encode_message",
    "parse_command_line",
]
