"""The Tour tab: the open folder's module map, and a tour of it written by the model."""

from __future__ import annotations

from agent_workspace.coding.repo_map import module_graph
from agent_workspace.coding.repo_tour import TourError, read_tour, write_tour
from agent_workspace.ui_gateway.gateway_common import GatewayError, GatewayReply
from agent_workspace.ui_gateway.gateway_state import GatewayState
from agent_workspace.ui_gateway.protocol import CommandEnvelope

TOUR_COMMANDS = frozenset({"tour.map", "tour.get", "tour.write"})
# Reading every code file of a large repository takes a second or two.
TOUR_QUERY_COMMANDS = frozenset({"tour.map", "tour.get"})
# The model writes the tour: with the other model calls.
TOUR_MODEL_COMMANDS = frozenset({"tour.write"})


class TourCommands(GatewayState):
    def _tour_command(self, command: CommandEnvelope) -> GatewayReply:
        if command.session_id is not None:
            raise GatewayError("invalid_session")
        root = self._open_folder()
        if command.type == "tour.map":
            result: dict[str, object] = {"map": module_graph(root)}
        elif command.type == "tour.get":
            result = {"tour": read_tour(root)}
        else:
            language = command.payload.get("language", "en-US")
            if not isinstance(language, str):
                raise GatewayError("invalid_command")
            try:
                result = {"tour": write_tour(self._quick_provider(), root, language)}
            except TourError as error:
                raise GatewayError(str(error)) from None
        return self._reply(f"{command.type}.result", result, session_id=None)


__all__ = ["TOUR_COMMANDS", "TOUR_MODEL_COMMANDS", "TOUR_QUERY_COMMANDS", "TourCommands"]
