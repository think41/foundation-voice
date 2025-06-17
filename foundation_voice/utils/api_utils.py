"""
Utility functions for API key management and configuration.
"""
import os
from typing import Optional
from loguru import logger


def get_api_key(service_name: str, config: Optional[dict] = None) -> str:
    """
    Get API key for a service from either environment variables or config.
    
    Args:
        service_name: Name of the service (e.g., 'openai', 'deepgram')
        config: Optional config dictionary that might contain the API key
        
    Returns:
        str: The API key
        
    Raises:
        ValueError: If API key is not found in either environment or config
    """
    # Convert service name to standard environment variable format
    env_var = f"{service_name.upper()}_API_KEY"
    
    # Try to get from environment first
    api_key = os.getenv(env_var)
    
    # If not in environment, try config
    if not api_key and config:
        api_key = config.get(f"{service_name.lower()}_api_key")
    
    if not api_key:
        error_msg = (
            f"{service_name.upper()} API key not found. "
            f"Please set the {env_var} environment variable "
            f"or provide it in the config."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return api_key
