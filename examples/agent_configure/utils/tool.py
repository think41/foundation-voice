from agents import function_tool, RunContextWrapper
from .context import MagicalNestContext

"""
Define your agent tools here

Example:

@function_tool(
    description_override='Placeholder'
)
def placeholder(ctx: RunContextWrapper, args):
    return 'Placeholder'
"""


@function_tool(
    description_override="Function called whenever an info about the child is received."
)
def update_basic_info(
    ctx: RunContextWrapper[MagicalNestContext],
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


@function_tool(
    description_override="Function called whenever an info about the room is received."
)
def update_room_data(
    ctx: RunContextWrapper[MagicalNestContext],
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


@function_tool(
    description_override="Function called whenever an info about the products is received."
)
def update_products(ctx: RunContextWrapper[MagicalNestContext], products: str = None):
    if products is not None:
        ctx.context.products = products

    return f"Products updated: {products}"


@function_tool
def search_tool(ctx: RunContextWrapper, query: str):
    return f"Searching for {query}"


tool_config = {
    "update_basic_info": update_basic_info,
    "update_room_data": update_room_data,
    "update_products": update_products,
    "search_tool": search_tool,
}
