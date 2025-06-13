"""
VectorDB Manager - A singleton class to manage ChromaDB client and related resources.
"""
from functools import wraps
import os
from typing import Optional, Dict, Any, List
import logging

import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv


# Configure logger for this module
logger = logging.getLogger(__name__)


def singleton(cls):
    """Singleton decorator to ensure only one instance of a class exists."""
    instances = {}
    
    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            logger.info("Creating new singleton instance of %s", cls.__name__)
            print(f"[Singleton] Creating new instance of {cls.__name__}")
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


@singleton
class VectorDBManager:
    """Singleton class to manage ChromaDB client and related resources."""
    
    def __init__(self):
        # Load environment variables from .env file if it exists
        load_dotenv()
        
        # Initialize components
        self.persistent_client = None
        self.embedding_function = None
        self.vector_db = None
        
        # Configuration
        self.chroma_persist_directory = os.getenv(
            "CHROMA_PERSIST_DIRECTORY",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "db")
        )
        self.chroma_collection_name = os.getenv("CHROMA_COLLECTION_NAME", "foundation_voice_kb")
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize ChromaDB client and related components."""
        try:
            self.persistent_client = chromadb.PersistentClient(path=self.chroma_persist_directory)
            self.embedding_function = OpenAIEmbeddings(model="text-embedding-3-small")
            self.vector_db = Chroma(
                client=self.persistent_client,
                collection_name=self.chroma_collection_name,
                embedding_function=self.embedding_function,
            )
            print("Successfully connected to persistent ChromaDB for RAG tool.")
        except Exception as e:
            print(f"Error initializing ChromaDB for RAG tool: {e}")
            self.vector_db = None
    
    def get_vector_db(self) -> Optional[Chroma]:
        """Get the vector database instance."""
        return self.vector_db
    
    def get_embedding_function(self) -> Optional[OpenAIEmbeddings]:
        """Get the embedding function instance."""
        return self.embedding_function
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection."""
        if not self.vector_db:
            return {"status": "error", "message": "Vector DB not initialized"}
        
        try:
            collection = self.vector_db._collection
            count = collection.count()
            return {
                "status": "success",
                "collection_name": self.chroma_collection_name,
                "documents_count": count,
                "persist_directory": self.chroma_persist_directory
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def similarity_search(self, query: str, k: int = 4, **kwargs) -> List[Any]:
        """Perform a similarity search on the vector database.
        
        Args:
            query: The query string
            k: Number of results to return
            **kwargs: Additional arguments to pass to the similarity search
            
        Returns:
            List of documents matching the query
        """
        if not self.vector_db:
            return []
        
        try:
            return self.vector_db.similarity_search(query, k=k, **kwargs)
        except Exception as e:
            print(f"Error during similarity search: {e}")
            return []


# # Create a global instance of the VectorDBManager
# vector_db_manager = VectorDBManager()

_vector_db_manager: Optional[VectorDBManager] = None

def _get_manager() -> VectorDBManager:
    global _vector_db_manager
    if _vector_db_manager is None:
        _vector_db_manager = VectorDBManager()
    return _vector_db_manager

# Convenience functions
def get_vector_db() -> Optional[Chroma]:
    """Get the vector database instance."""
    return _get_manager().get_vector_db()

def get_embedding_function() -> Optional[OpenAIEmbeddings]:
    """Get the embedding function instance."""
    return _get_manager().get_embedding_function()

def get_collection_info() -> Dict[str, Any]:
    """Get information about the current collection."""
    return _get_manager().get_collection_info()

def similarity_search(query: str, k: int = 4, **kwargs) -> List[Any]:
    """Perform a similarity search on the vector database."""
    return _get_manager().similarity_search(query, k=k, **kwargs)
