from __future__ import annotations

import hashlib
from uuid import uuid4

from agent_workspace.application.ports import EventStore
from agent_workspace.core.events import Event
from agent_workspace.core.models import (
    MAX_IMAGES_PER_MESSAGE,
    MAX_IMAGES_TOTAL_BYTES,
    BinaryArtifact,
    ChatMessage,
    ImagePart,
    ImagePartError,
    Role,
    validate_image_parts,
)

MAX_TURN_INPUTS = 16
MAX_TURN_INPUT_CHARS = 100_000
MAX_PENDING_INPUT_BYTES = 512 * 1024


class TurnInputBuffer:
    """Persist receipt immediately, then apply only between complete model/tool rounds."""

    def __init__(self, store: EventStore, session_id: str, correlation_id: str) -> None:
        self.store = store
        self.session_id = session_id
        self.correlation_id = correlation_id
        self.accepting = True
        self.pending = store.list_pending_turn_inputs(session_id)

    def receive(
        self,
        prompt: str,
        turn_id: str | None,
        input_id: str | None = None,
        *,
        images: tuple[ImagePart, ...] = (),
    ) -> Event:
        if not self.accepting or (turn_id is not None and turn_id != self.correlation_id):
            raise RuntimeError("turn_not_active")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_TURN_INPUT_CHARS:
            raise ValueError("invalid_prompt")
        prompt = prompt.strip()
        validate_image_parts(images)
        image_metadata = [
            {
                "media_type": image.media_type,
                "sha256": hashlib.sha256(image.data).hexdigest(),
                "bytes": len(image.data),
            }
            for image in images
        ]
        if input_id is not None:
            if (
                not isinstance(input_id, str)
                or not input_id
                or len(input_id) > 128
                or any(
                    not (char.isascii() and (char.isalnum() or char in "-_.")) for char in input_id
                )
            ):
                raise ValueError("invalid_turn_input_id")
            previous = self.store.get_event(input_id)
            if previous is not None:
                if (
                    previous.type != "turn.input.received"
                    or previous.session_id != self.session_id
                    or previous.correlation_id != self.correlation_id
                    or previous.data.get("prompt") != prompt
                    or previous.data.get("images", []) != image_metadata
                ):
                    raise ValueError("turn_input_conflict")
                return previous
        pending_bytes = sum(len(str(e.data["prompt"]).encode("utf-8")) for e in self.pending)
        pending_image_bytes = sum(
            len(image.data)
            for event in self.pending
            for image in self._images_for_receipt(event)
        )
        if (
            len(self.pending) >= MAX_TURN_INPUTS
            or pending_bytes + len(prompt.encode("utf-8")) > MAX_PENDING_INPUT_BYTES
            or pending_image_bytes + sum(len(image.data) for image in images)
            > MAX_IMAGES_TOTAL_BYTES
        ):
            raise RuntimeError("turn_input_full")
        received = Event(
            id=input_id or str(uuid4()),
            session_id=self.session_id,
            type="turn.input.received",
            data={"prompt": prompt, **({"images": image_metadata} if images else {})},
            correlation_id=self.correlation_id,
        )
        if images:
            image_events = tuple(
                Event(
                    session_id=self.session_id,
                    type="image.attached",
                    data={
                        **metadata,
                        "source": "user",
                        "attempt_id": "user",
                        "path": "user_attachment",
                        "input_id": received.id,
                    },
                    correlation_id=self.correlation_id,
                    causation_id=received.id,
                )
                for metadata in image_metadata
            )
            artifacts = tuple(
                BinaryArtifact(hashlib.sha256(image.data).hexdigest(), image.data)
                for image in images
            )
            event = self.store.append_many_with_artifacts((received, *image_events), artifacts)[0]
        else:
            event = self.store.append(received)
        # No await between the durable write and admitting the input: completion
        # cannot race with receipt while this code runs on the owning event loop.
        self.pending.append(event)
        return event

    def apply(self) -> tuple[list[ChatMessage], list[Event]]:
        if not self.pending:
            return [], []
        messages: list[ChatMessage] = []
        events: list[Event] = []
        count = len(self.pending)
        for received in self.pending:
            images = self._images_for_receipt(received)
            metadata = (
                {
                    "agent_workspace.images": [
                        {
                            "media_type": image.media_type,
                            "sha256": hashlib.sha256(image.data).hexdigest(),
                        }
                        for image in images
                    ]
                }
                if images
                else {}
            )
            message = ChatMessage(
                role=Role.USER,
                content=str(received.data["prompt"]),
                images=images,
                provider_metadata=metadata,
            )
            messages.append(message)
            events.extend(
                (
                    Event(
                        session_id=self.session_id,
                        type="message.created",
                        data={
                            "role": "user",
                            "content": message.content,
                            "reasoning": "",
                            "tool_call_id": None,
                            "tool_calls": [],
                            "trust": message.trust.value,
                            "sensitivity": message.sensitivity.value,
                            "provider_metadata": metadata,
                            "input_id": received.id,
                        },
                        correlation_id=self.correlation_id,
                        causation_id=received.id,
                    ),
                    Event(
                        session_id=self.session_id,
                        type="turn.input.applied",
                        data={"input_id": received.id},
                        correlation_id=self.correlation_id,
                        causation_id=received.id,
                    ),
                )
            )
        stored = self.store.append_many(tuple(events))
        # The applied marker and user message commit atomically. A crash can
        # recover pending receipt, or load the applied message, but never both.
        del self.pending[:count]
        return messages, stored

    def _images_for_receipt(self, received: Event) -> tuple[ImagePart, ...]:
        raw_images = received.data.get("images", [])
        if not isinstance(raw_images, list) or len(raw_images) > MAX_IMAGES_PER_MESSAGE:
            raise ImagePartError("Stored user image metadata is invalid")
        images: list[ImagePart] = []
        for metadata in raw_images:
            if not isinstance(metadata, dict):
                raise ImagePartError("Stored user image metadata is invalid")
            digest = metadata.get("sha256")
            media_type = metadata.get("media_type")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or not isinstance(media_type, str)
            ):
                raise ImagePartError("Stored user image metadata is invalid")
            artifact = self.store.get_binary_artifact(digest)
            if artifact is None or hashlib.sha256(artifact.content).hexdigest() != digest:
                raise ImagePartError(
                    "Stored user image is unavailable or failed integrity verification"
                )
            images.append(ImagePart(media_type, artifact.content))
        resolved = tuple(images)
        validate_image_parts(resolved)
        return resolved

    def close(self) -> None:
        self.accepting = False
