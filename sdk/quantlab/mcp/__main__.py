"""MCP Bridge entry point — ``python -m quantlab.mcp``."""


def main() -> None:
    """Boot the MCP server and start listening.

    Delegates to ``quantlab.mcp.bridge.main`` once the bridge module
    exists (PR 2 of the stacked change).
    """
    from quantlab.mcp.bridge import main as bridge_main

    bridge_main()


if __name__ == "__main__":
    main()
