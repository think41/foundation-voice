# foundation_voice/scripts/ingest.py
import os
import shutil
import chromadb
from dotenv import load_dotenv

# LangChain components for document processing
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# Load environment variables from .env file if it exists
load_dotenv()

class IngestionService:
    """Handles the document ingestion pipeline: loading, splitting, embedding, and storing documents."""

    def __init__(
        self,
        document_source_directory: str = None,
        chroma_persist_directory: str = None,
        chroma_collection_name: str = None,
        openai_api_key: str = None,
    ):
        """
        Initializes the IngestionService with configuration for document processing.

        Args:
            document_source_directory: Path to the directory containing source documents.
                                       Defaults to project_root/knowledge_base_documents.
            chroma_persist_directory: Path to the directory where ChromaDB should persist data.
                                      Defaults to project_root/db.
            chroma_collection_name: Name of the collection in ChromaDB.
                                    Defaults to 'foundation_voice_kb'.
            openai_api_key: OpenAI API key. Defaults to value from OPENAI_API_KEY env var.
        """
        self.document_source_directory = document_source_directory or os.getenv(
            "DOCUMENT_SOURCE_DIRECTORY",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge_base_documents")
        )
        self.chroma_persist_directory = chroma_persist_directory or os.getenv(
            "CHROMA_PERSIST_DIRECTORY",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "db")
        )
        self.chroma_collection_name = chroma_collection_name or os.getenv(
            "CHROMA_COLLECTION_NAME", "foundation_voice_kb"
        )
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in your .env file or pass it as an argument."
            )

    def _ensure_db_directory(self) -> None:
        """Ensures the database directory exists and has the correct permissions."""
        os.makedirs(self.chroma_persist_directory, exist_ok=True)


    def _load_documents(self) -> list:
        """Loads documents from the configured source directory using specific loaders for file types."""
        print(f"Loading documents from '{self.document_source_directory}'...")
        
        documents = []

        # Load .txt files
        txt_loader = DirectoryLoader(
            self.document_source_directory,
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'},
            show_progress=True,
            use_multithreading=False,
            silent_errors=False, # Explicitly show errors for .txt loading
        )
        try:
            txt_documents = txt_loader.load()
            if txt_documents:
                print(f"Loaded {len(txt_documents)} .txt document(s).")
                documents.extend(txt_documents)
            else:
                print("No .txt documents found or loaded.")
        except Exception as e:
            print(f"Error loading .txt files: {e}")

        # Load .md files
        md_loader = DirectoryLoader(
            self.document_source_directory,
            glob="**/*.md",
            loader_cls=TextLoader,  # TextLoader can also handle .md for text content
            loader_kwargs={'encoding': 'utf-8'},
            show_progress=True,
            use_multithreading=False,
            silent_errors=False, # Explicitly show errors for .md loading
        )
        try:
            md_documents = md_loader.load()
            if md_documents:
                print(f"Loaded {len(md_documents)} .md document(s).")
                documents.extend(md_documents)
            else:
                print("No .md documents found or loaded.")
        except Exception as e:
            print(f"Error loading .md files: {e}")

        if not documents:
            print("No documents loaded from any source.")
            return []
        
        print(f"Total documents loaded: {len(documents)}.")
        return documents

    def _split_documents(self, documents: list) -> list:
        """Splits the loaded documents into smaller chunks."""
        if not documents:
            return []
        print("Splitting documents into smaller chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=250,  # Smaller chunk size for more granular context
            chunk_overlap=50,  # Smaller overlap
            length_function=len,
        )
        chunks = text_splitter.split_documents(documents)
        print(f"Split documents into {len(chunks)} chunks.")
        return chunks

    def _generate_and_store_embeddings(self, chunks: list) -> Chroma:
        """Generates embeddings for the chunks and stores them in ChromaDB."""
        if not chunks:
            print("No chunks to process for embedding.")
            return None

        print("Generating embeddings and storing in ChromaDB...")
        embedding_function = OpenAIEmbeddings(
            model="text-embedding-3-small", openai_api_key=self.openai_api_key
        )

        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embedding_function,
            collection_name=self.chroma_collection_name,
            persist_directory=self.chroma_persist_directory,
        )
        return vector_store

    def run_ingestion(self) -> None:
        """Runs the complete document ingestion pipeline."""
        print("--- Starting Document Ingestion Pipeline ---")
        try:
            # Ensure the DB directory exists and is writable
            self._ensure_db_directory()

            documents = self._load_documents()
            if not documents:
                print("Ingestion halted as no documents were loaded.")
                return

            chunks = self._split_documents(documents)
            if not chunks:
                print("Ingestion halted as no chunks were created from documents.")
                return

            vector_store = self._generate_and_store_embeddings(chunks)

            if vector_store:
                print("--- Document Ingestion Complete ---")
                print(f"Vector database stored in: '{self.chroma_persist_directory}'")
                print(
                    f"Collection '{self.chroma_collection_name}' contains {vector_store._collection.count()} embedded chunks."
                )
            else:
                print("--- Document Ingestion Failed or No Data Processed ---")
        except Exception as e:
            print(f"--- Document Ingestion Failed: {str(e)} ---")
            raise

