from typing import Any
from .context import MagicalNestContext


AGENTS_AVAILABLE = False
function_tool = None
RunContextWrapper = None

try:
    from agents import function_tool as ft, RunContextWrapper as RCW
    function_tool = ft
    RunContextWrapper = RCW
    AGENTS_AVAILABLE = True
except ImportError:
    print("INFO: 'agents' package not found. Tools specifically requiring 'agents.function_tool' or 'RunContextWrapper' for 'openai_agents' provider might not work as expected. "
          "To use 'openai_agents' provider features, install with: pip install foundation-voice[openai_agents]")
    # Fallback for type hints if RunContextWrapper is not available
    RunContextWrapper_hint = "RunContextWrapper[MagicalNestContext]" 
else:
    # If import is successful, use the real type for hints
    RunContextWrapper_hint = RunContextWrapper[MagicalNestContext]

"""
Define your agent tools here

Example:

@function_tool(
    description_override='Placeholder'
)
def placeholder(ctx: RunContextWrapper, args):
    return 'Placeholder'
"""


def update_basic_info(
    ctx: RunContextWrapper_hint,
    name: str = None,
    age: str = None,
    gender: str = None,
    room_type: str = None,
):
    if name is not None:
        ctx.context.name = name
    if age is not None:
        ctx.context.age = age
    if gender is not None:
        ctx.context.gender = gender

    if room_type is not None:
        ctx.context.room_type = room_type

    return f"Basic information updated: {name}, {age}, {gender}, {room_type}"


def update_room_data(
    ctx: RunContextWrapper_hint,
    colors: str = None,
    activities: str = None,
    themes: str = None,
    constraints: str = None,
):
    if colors is not None:
        ctx.context.colors = colors
    if activities is not None:
        ctx.context.activities = activities
    if themes is not None:
        ctx.context.themes = themes
    if constraints is not None:
        ctx.context.constraints = constraints

    return f"Room data updated: {colors}, {activities}, {themes}, {constraints}"


def update_products(ctx: RunContextWrapper_hint, products: str = None):
    if products is not None:
        ctx.context.products = products

    return f"Products updated: {products}"


def search_tool(query: str):
    return f"Searching for {query}"


tool_config = {
    "update_basic_info": update_basic_info,
    "update_room_data": update_room_data,
    "update_products": update_products,
    "search_tool": search_tool,
}
