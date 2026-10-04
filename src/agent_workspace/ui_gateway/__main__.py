import multiprocessing
import sys

if __name__ == "__main__":
    if sys.argv[1:] == ["--agent-workspace-tool-worker"]:
        from agent_workspace.tools.process_worker import run_serialized_tool_worker

        raise SystemExit(run_serialized_tool_worker())

    # Frozen multiprocessing children re-enter this module. Divert them before
    # importing the gateway graph: those imports initialize runtime dependencies
    # that a worker neither needs nor may safely initialize during spawn.
    multiprocessing.freeze_support()

    from agent_workspace.ui_gateway.server import main

    raise SystemExit(main())
