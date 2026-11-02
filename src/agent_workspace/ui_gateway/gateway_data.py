"""Settings → Data and backups: what is stored, the backups, and putting one back."""

from __future__ import annotations

from agent_workspace.ui_gateway.data_care import (
    DataCareError,
    create_backup_now,
    database_health,
    last_restore,
    list_backups,
    request_fresh_start,
    request_restore,
    storage_usage,
)
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

DATA_COMMANDS = frozenset({"data.status", "data.backup", "data.restore", "data.fresh_start"})
# Walking the folder and checking the database take a moment on a long history.
DATA_QUERY_COMMANDS = frozenset({"data.status"})
# A backup, and the check of one, take as long as copying the database.
DATA_LONG_COMMANDS = frozenset({"data.backup", "data.restore"})


class DataCommands(GatewayState):
    def _data_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        database = self._database
        try:
            if command.type == "data.status":
                self._require_payload(command, set())
                result: dict[str, object] = {
                    "folder": str(database.parent),
                    "health": database_health(database),
                    "usage": storage_usage(database),
                    "backups": list_backups(database),
                    "lastRestore": last_restore(database),
                }
            elif command.type == "data.backup":
                self._require_payload(command, set())
                result = {"backup": create_backup_now(database)}
            else:
                # The next start carries these out, while nothing has the database open.
                if self._busy:
                    raise GatewayError("runtime_busy")
                if command.type == "data.restore":
                    self._require_payload(command, {"name"})
                    request_restore(database, command.payload.get("name"))
                else:
                    self._require_payload(command, set())
                    request_fresh_start(database)
                result = {"restartRequired": True}
        except DataCareError as error:
            raise GatewayError(str(error)) from None
        return self._reply(f"{command.type}.result", result, session_id=None)


__all__ = ["DATA_COMMANDS", "DATA_LONG_COMMANDS", "DATA_QUERY_COMMANDS", "DataCommands"]
