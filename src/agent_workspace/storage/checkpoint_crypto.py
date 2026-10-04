from __future__ import annotations

import hashlib

from agent_workspace.credentials import protect_current_user_data, unprotect_current_user_data

_CHECKPOINT_ENTROPY_DOMAIN = b"AgentWorkspace/file-checkpoint/v1\0"


def protect_checkpoint_preimage(
    preimage: bytes,
    *,
    attempt_id: str,
    session_id: str,
    workspace: str,
    relative_path: str,
) -> bytes:
    return protect_current_user_data(
        preimage,
        entropy=_checkpoint_entropy(attempt_id, session_id, workspace, relative_path),
    )


def unprotect_checkpoint_preimage(
    protected_preimage: bytes,
    *,
    attempt_id: str,
    session_id: str,
    workspace: str,
    relative_path: str,
) -> bytes:
    return unprotect_current_user_data(
        protected_preimage,
        entropy=_checkpoint_entropy(attempt_id, session_id, workspace, relative_path),
    )


def _checkpoint_entropy(
    attempt_id: str,
    session_id: str,
    workspace: str,
    relative_path: str,
) -> bytes:
    fields = "\0".join((attempt_id, session_id, workspace, relative_path)).encode("utf-8")
    return hashlib.sha256(_CHECKPOINT_ENTROPY_DOMAIN + fields).digest()
