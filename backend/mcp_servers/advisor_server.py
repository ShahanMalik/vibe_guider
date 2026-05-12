from mcp.server.fastmcp import FastMCP

mcp=FastMCP(
 "tool_advisor"
)

@mcp.tool()
def suggest_database(scale:str):

    if "startup" in scale:
        return "PostgreSQL"

    if "large" in scale:
        return "PostgreSQL + Redis"

    return "PostgreSQL"


@mcp.tool()
def suggest_backend(use_case:str):

    if "ai" in use_case.lower():
        return "FastAPI"

    return "Django"


if __name__=="__main__":
    mcp.run()