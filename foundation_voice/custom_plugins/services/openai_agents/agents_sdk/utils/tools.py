from agents import function_tool, RunContextWrapper


"""
Define your agent tools here

Example:

@function_tool(
    description_override='Placeholder'
)
def placeholder(ctx: RunContextWrapper):
    return 'Placeholder'
"""


@function_tool
def weather_tool(ctx: RunContextWrapper, location: str):
    return f"Weather in {location} is 32 degrees celsius"


# Add your tools here. Key: Function_name; Value: Reference to function
tool_config = {"weather_tool": weather_tool}
