"""
Utility functions for API key management and configuration.
"""
import os
from typing import Optional
from loguru import logger



def _raise_missing_api_key(provider_name: str, key_name: str):
    """
    Raises a ValueError indicating a missing API key for a specific provider.

    Args:
        provider_name: The name of the provider (e.g., "OpenAI", "Cerebras").
        key_name: The name of the environment variable for the API key (e.g., "OPENAI_API_KEY").
    """
    raise ValueError(
        f"Missing API key for {provider_name} provider. "
        f"Please set the {key_name} environment variable or provide 'api_key' in the configuration."
    )