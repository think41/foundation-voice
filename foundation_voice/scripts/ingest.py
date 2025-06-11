# scripts/ingest.py
import os
import shutil
import chromadb
from dotenv import load_dotenv

# LangChain components for document processing
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader # Add PyPDFLoader if using PDFs
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma # Updated import

# Load environment variables from .env file if it exists
load_dotenv()

# --- Configuration ---
# Document source directory (default: project_root/knowledge_base_documents)
DOCUMENT_SOURCE_DIRECTORY = os.getenv(
    "DOCUMENT_SOURCE_DIRECTORY",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge_base_documents")
)

# Chroma DB persistence directory (default: project_root/db)
CHROMA_PERSIST_DIRECTORY = os.getenv(
    "CHROMA_PERSIST_DIRECTORY",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "db")
)

# Chroma collection name
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "foundation_voice_kb")

def main():
    print("--- Starting Document Ingestion Pipeline ---")

    # --- Clean up old database ---
    if os.path.exists(CHROMA_PERSIST_DIRECTORY):
        print(f"Removing existing database at '{CHROMA_PERSIST_DIRECTORY}'...")
        shutil.rmtree(CHROMA_PERSIST_DIRECTORY)
        print("Existing database removed.")

    # 1. LOAD DOCUMENTS
    print(f"Loading documents from '{DOCUMENT_SOURCE_DIRECTORY}'...")
    # Using DirectoryLoader to load all .md and .txt files.
    # You can add more loaders or specify different globs.
    loader = DirectoryLoader(
        DOCUMENT_SOURCE_DIRECTORY,
        glob="**/*[.md,.txt]", # Adjust glob to include other file types if needed
        show_progress=True,
        use_multithreading=False  # Disabled to prevent hanging
    )

    documents = loader.load()

    if not documents:
        print("No documents found. Please add documents to the source directory.")
        return
    print(f"Loaded {len(documents)} document(s).")

    # 2. SPLIT DOCUMENTS
    print("Splitting documents into smaller chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=250,  # Smaller chunk size for more granular context
        chunk_overlap=50,   # Smaller overlap
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split documents into {len(chunks)} chunks.")

    # 3. CREATE EMBEDDINGS and 4. STORE IN VECTOR DATABASE (ChromaDB)
    print("Generating embeddings and storing in ChromaDB...")
    # Ensure OPENAI_API_KEY is set in your .env file
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in environment variables.")

    embedding_function = OpenAIEmbeddings(model="text-embedding-3-small") # Uses the API key from env

    # Create a persistent ChromaDB client
    # This will save the database to the `CHROMA_PERSIST_DIRECTORY`
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_function,
        collection_name=CHROMA_COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIRECTORY
    )
    vector_store.persist() # Ensure data is written to disk

    print("--- Document Ingestion Complete ---")
    print(f"Vector database stored in: '{CHROMA_PERSIST_DIRECTORY}'")
    print(f"Collection '{CHROMA_COLLECTION_NAME}' contains {vector_store._collection.count()} embedded chunks.")

if __name__ == "__main__":
    main()