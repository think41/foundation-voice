from agents import function_tool, RunContextWrapper
from .context import MagicalNestContext

import os # Add this if not already present
import chromadb # Add this
from langchain_openai import OpenAIEmbeddings # Add this
from langchain_chroma import Chroma # Updated import
from dotenv import load_dotenv
from agents import function_tool, RunContextWrapper


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



# --- Configuration for accessing the Vector DB ---
# Load environment variables from .env file if it exists
load_dotenv()

# Chroma DB persistence directory (default: project_root/db)
CHROMA_PERSIST_DIRECTORY = os.getenv(
    "CHROMA_PERSIST_DIRECTORY",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "db")
)

# Chroma collection name
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "foundation_voice_kb")

# --- Initialize ChromaDB client and embedding function ---
# This part is initialized ONCE when the module is loaded, not on every call.
try:
    persistent_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    embedding_function_for_retrieval = OpenAIEmbeddings(model="text-embedding-3-small") # Using the newer embedding model
    vector_db = Chroma(
        client=persistent_client,
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding_function_for_retrieval,
    )
    print("Successfully connected to persistent ChromaDB for RAG tool.")
except Exception as e:
    print(f"Error initializing ChromaDB for RAG tool: {e}. RAG tool might not work.")
    vector_db = None
# --- End ChromaDB Initialization ---


# ... (keep your existing tool definitions like update_basic_info)

@function_tool(
    description_override="Searches the internal knowledge base for specific information to answer user questions about products, policies, or company details. Use this tool when you need to find factual information not readily available in the conversation history."
)
def retrieve_from_knowledge_base(query: str) -> str:
    """
    Retrieves relevant information from the knowledge base based on the user's query.
    The LLM will use this information to answer the user.
    """
    print(f"[RAG Tool] Received query: '{query}'")

    if vector_db is None:
        return "Knowledge base is currently unavailable."

    try:
        # Manually embed the query to use the native ChromaDB client
        query_embedding = embedding_function_for_retrieval.embed_query(query)

        # Query the collection directly.
        results = vector_db._collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )

        # Define a relevance threshold. Testing shows that specific queries can have a higher distance.
        # We are setting this to 1.3 to be less strict.
        RELEVANCE_THRESHOLD = 1.3

        # Filter documents based on the threshold.
        relevant_docs = []
        if results and results.get('documents') and results['documents'][0]:
            for i, doc_content in enumerate(results['documents'][0]):
                distance = results['distances'][0][i]
                if distance < RELEVANCE_THRESHOLD:
                    relevant_docs.append(doc_content)

        if not relevant_docs:
            print("[RAG Tool] No relevant documents found.")
            return "No relevant information found in the knowledge base for this query."

        # Format the retrieved documents into a string context for the LLM
        context_str = "Based on the knowledge base, here's some relevant information:\n"
        for i, doc_content in enumerate(relevant_docs):
            context_str += f"Context {i+1}: {doc_content}\n\n"

        print(f"[RAG Tool] Returning context:\n{context_str[:500]}...") # Log a snippet
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
    "retrieve_from_knowledge_base": retrieve_from_knowledge_base # Add your new tool
}