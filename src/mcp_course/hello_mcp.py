from random import choice

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Random Name")


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


NICKNAMES = {
    "Alice": ["Ali", "Allie", "Lissy"],
    "Bob": ["Bobby", "Rob", "Bobster"],
    "Charlie": ["Chuck", "Chaz", "Chip"],
    "Diana": ["Di", "Dee", "Princess"],
    "Eve": ["Evie", "Eva"],
    "Frank": ["Frankie", "Fran", "Big F"],
    "Grace": ["Gracie", "Gray"],
    "Hank": ["Hanky", "H-Man"],
    "Ivy": ["Ives", "Poison Ivy"],
    "Jack": ["Jackie", "Jacko", "J"],
}

GENERIC_SUFFIXES = ["y", "ie", "ster", "o"]


@mcp.tool()
def get_nickname(name: str) -> str:
    """Get a random nickname for a person's name.

    Args:
        name: The person's name. Known names get a curated nickname;
            any other name gets a generated one.
    """
    name = name.strip().title()
    if name in NICKNAMES:
        return choice(NICKNAMES[name])
    return name[:3] + choice(GENERIC_SUFFIXES)


if __name__ == "__main__":
    mcp.run()
