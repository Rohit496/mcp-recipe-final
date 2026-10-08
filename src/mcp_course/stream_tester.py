from random import choice

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Random Name Tester", version="2.0.0")


DEFAULT_NAMES = [
    "Alice",
    "Bob",
    "Charlie",
    "Diana",
    "Eve",
    "Frank",
    "Grace",
    "Hank",
    "Ivy",
    "Jack",
]


@mcp.tool()
def get_random_name(names: list[str] | None = None) -> str:
    """Get a random person's name.

    Args:
        names: Optional list of names to choose from. If omitted or empty,
            a predefined list of names is used.
    """
    return choice(names or DEFAULT_NAMES)


if __name__ == "__main__":
    # Serves at http://127.0.0.1:8000/mcp
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
