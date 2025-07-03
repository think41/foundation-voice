from agents import function_tool, RunContextWrapper
from .context import MagicalNestContext
from foundation_voice.utils.vector_db import similarity_search

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


def update_products(ctx: RunContextWrapper[MagicalNestContext], products: str = None):
    if products is not None:
        ctx.context.products = products

    return f"Products updated: {products}"


def search_tool(query: str):
    return f"Searching for {query}"



# VectorDB is now managed by the VectorDBManager singleton
# The manager handles initialization and provides access to the vector DB and embedding function

def retrieve_from_knowledge_base(query: str) -> str:
    """
    Retrieves relevant information from the knowledge base based on the user's query.
    The LLM will use this information to answer the user.
    for specific information to answer user questions about products, policies, or company details. Use this tool when you need to find factual information not readily available in the conversation history.
    """
    print(f"[RAG Tool] Received query: '{query}'")

    try:
        # Use the singleton VectorDBManager to get relevant documents
        results = similarity_search(query, k=3)

        if not results:
            print("[RAG Tool] No relevant documents found.")
            return "No relevant information found in the knowledge base for this query."

        # Format the retrieved documents into a string context for the LLM
        context_str = "Based on the knowledge base, here's some relevant information:\n"
        for i, doc in enumerate(results):
            context_str += f"Context {i+1}: {doc.page_content if hasattr(doc, 'page_content') else doc}\n\n"

        print(f"[RAG Tool] Returning context:\n{context_str[:500]}...")  # Log a snippet
        return context_str.strip()

    except Exception as e:
        print(f"[RAG Tool] Error during retrieval: {e}")
        return f"An error occurred while trying to access the knowledge base: {str(e)}"

# ... (at the end of the file, update tool_config)
tool_config = {
    "update_basic_info": update_basic_info,
    "update_room_data": update_room_data,
    "update_products": update_products,
    "search_tool": search_tool,
    "retrieve_from_knowledge_base": retrieve_from_knowledge_base,
}
