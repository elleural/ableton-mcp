"""AbletonMCP server entry point (`ableton-mcp`)."""
from . import tools  # noqa: F401  (importing the package registers every tool)
from .app import mcp
from .connection import AbletonConnection, AbletonError, get_connection  # noqa: F401  (public API)


def main():
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
