"""Desktop notification action buttons.

Notification cards may attach up to a small number of quick actions (open,
dismiss-all, snooze, run, ...). This module validates button definitions,
matches notification kinds against an action policy, and renders the effective
button list for a notification payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_ACTIONS_PER_NOTIFICATION = 3

_KIND_ACTIONS: dict[str, tuple[dict[str, str], ...]] = {
    "approval_required": (
        {"id": "approve", "label": "Approve"},
        {"id": "reject", "label": "Reject"},
        {"id": "view", "label": "View details"},
    ),
    "webhook_failed": (
        {"id": "retry", "label": "Retry delivery"},
        {"id": "view", "label": "View queue"},
    ),
    "release_ready": (
        {"id": "promote", "label": "Promote"},
        {"id": "snooze", "label": "Snooze"},
    ),
}


class NotificationActionsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NotificationActionButton:
    id: str
    label: str
    style: str = "default"
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.label.strip():
            raise NotificationActionsError("notification action id and label may not be empty")
        if self.style not in {"default", "primary", "danger", "quiet"}:
            raise NotificationActionsError(f"notification action style {self.style!r} is invalid")

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "style": self.style,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass(frozen=True, slots=True)
class NotificationActionPolicy:
    kind_actions: dict[str, tuple[NotificationActionButton, ...]]
    deny_actions: frozenset[str] = frozenset()

    def buttons_for(self, kind: str) -> tuple[NotificationActionButton, ...]:
        if kind not in self.kind_actions:
            return ()
        return tuple(
            button for button in self.kind_actions[kind] if button.id not in self.deny_actions
        )


def notification_action_buttons(
    kind: str,
    *,
    policy: NotificationActionPolicy | None = None,
    allowed_action_ids: set[str] | frozenset[str] | None = None,
) -> tuple[NotificationActionButton, ...]:
    """Return the effective action buttons for one notification.

    ``allowed_action_ids`` restricts the policy's buttons further (for example
    based on the user's permission level); ``None`` means no restriction.
    """
    source = policy.kind_actions if policy is not None else _default_policy().kind_actions
    candidates = source.get(kind, ())
    buttons: list[NotificationActionButton] = []
    for button in candidates:
        if allowed_action_ids is not None and button.id not in allowed_action_ids:
            continue
        buttons.append(button)
        if len(buttons) >= _MAX_ACTIONS_PER_NOTIFICATION:
            break
    return tuple(buttons)


def validate_notification_actions(
    buttons: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[NotificationActionButton, ...]:
    seen: set[str] = set()
    parsed: list[NotificationActionButton] = []
    for raw in buttons:
        if not isinstance(raw, dict):
            raise NotificationActionsError("notification action must be an object")
        try:
            button = NotificationActionButton(
                id=str(raw["id"]),
                label=str(raw["label"]),
                style=str(raw.get("style", "default")),
                requires_confirmation=bool(raw.get("requires_confirmation", False)),
            )
        except NotificationActionsError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise NotificationActionsError("notification action is invalid") from exc
        if button.id in seen:
            raise NotificationActionsError(f"duplicate notification action id {button.id!r}")
        seen.add(button.id)
        parsed.append(button)
    if len(parsed) > _MAX_ACTIONS_PER_NOTIFICATION:
        raise NotificationActionsError(
            f"notifications may have at most {_MAX_ACTIONS_PER_NOTIFICATION} actions"
        )
    return tuple(parsed)


def _default_policy() -> NotificationActionPolicy:
    return NotificationActionPolicy(
        kind_actions={
            kind: tuple(
                NotificationActionButton(
                    id=str(item["id"]),
                    label=str(item["label"]),
                    style="primary" if index == 0 else "default",
                )
                for index, item in enumerate(actions)
            )
            for kind, actions in _KIND_ACTIONS.items()
        }
    )


__all__ = [
    "NotificationActionButton",
    "NotificationActionPolicy",
    "NotificationActionsError",
    "notification_action_buttons",
    "validate_notification_actions",
]
