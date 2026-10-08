from typing import Annotated

from mcp.server.mcpserver import MCPServer, UserMessage
from pydantic import Field

mcp = MCPServer("Prompt Tester")


@mcp.prompt(
    name="topic_analysis",
    title="Topic Analysis",
    description="Generate a prompt for a detailed analysis of a topic, ending with a concise summary.",
)
def topic_analysis(
    topic: Annotated[str, Field(min_length=1, description="The topic to analyze.")],
) -> list[UserMessage]:
    """Return a prompt asking for a detailed analysis of `topic`."""
    topic = topic.strip()
    return [
        UserMessage(
            f"Do a comprehensive, detailed analysis of the topic: {topic}.\n\n"
            "Requirements:\n"
            "- Cover all relevant aspects of the topic thoroughly.\n"
            "- Finish with a concise summary that highlights the most important findings."
        )
    ]


if __name__ == "__main__":
    mcp.run()
