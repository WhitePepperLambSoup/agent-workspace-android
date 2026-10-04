"""Application orchestration and public use cases."""

from typing import Any

__all__ = [
    "AgentRunner",
    "ApplicationService",
    "CollaborationCoordinator",
    "CollaborationRoute",
    "DeliveryLoop",
    "EventBus",
    "MultiProviderRuntime",
    "RunResult",
    "RuntimeDeliveryLoop",
    "build_multi_provider_runtime",
]


def __getattr__(name: str) -> Any:
    if name == "EventBus":
        from .event_bus import EventBus

        return EventBus
    if name in {"AgentRunner", "RunResult"}:
        from .runner import AgentRunner, RunResult

        return {"AgentRunner": AgentRunner, "RunResult": RunResult}[name]
    if name == "ApplicationService":
        from .service import ApplicationService

        return ApplicationService
    if name in {"CollaborationCoordinator", "CollaborationRoute"}:
        from .collaboration import CollaborationCoordinator, CollaborationRoute

        return {
            "CollaborationCoordinator": CollaborationCoordinator,
            "CollaborationRoute": CollaborationRoute,
        }[name]
    if name == "DeliveryLoop":
        from .delivery import DeliveryLoop

        return DeliveryLoop
    if name in {"MultiProviderRuntime", "RuntimeDeliveryLoop", "build_multi_provider_runtime"}:
        from .multi_runtime import (
            MultiProviderRuntime,
            RuntimeDeliveryLoop,
            build_multi_provider_runtime,
        )

        return {
            "MultiProviderRuntime": MultiProviderRuntime,
            "RuntimeDeliveryLoop": RuntimeDeliveryLoop,
            "build_multi_provider_runtime": build_multi_provider_runtime,
        }[name]
    raise AttributeError(name)
