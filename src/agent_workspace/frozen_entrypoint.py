from __future__ import annotations

import multiprocessing
import sys
from collections.abc import Sequence
from pathlib import Path


def main(
    argv: Sequence[str] | None = None,
    *,
    executable: str | None = None,
) -> int:
    multiprocessing.freeze_support()
    executable_name = Path(executable or sys.executable).stem.casefold()
    if executable_name == "agent-workspace":
        from agent_workspace.cli import main as cli_main

        return cli_main(list(argv) if argv is not None else None)
    raise RuntimeError(f"unknown frozen entry point: {executable_name}")


if __name__ == "__main__":
    raise SystemExit(main())
