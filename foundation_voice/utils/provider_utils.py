"""
Utility functions for provider creation and management.
"""

from importlib import import_module
from loguru import logger


def import_provider_service(module_path: str, class_name: str, extra: str):
    """
    Dynamically imports a service class from a module, handling ImportErrors.

    Args:
        module_path: The dot-separated path to the module (e.g., "pipecat.services.openai.tts").
        class_name: The name of the class to import (e.g., "OpenAITTSService").
        extra: The name of the pip extra to recommend for installation (e.g., "openai").

    Returns:
        The imported class.

    Raises:
        ImportError: If the module or class cannot be imported.
    """
    try:
        module = import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        error_message = (
            f"{class_name} dependencies not found. "
            f"Install with: pip install foundation-voice[{extra}]"
        )
        logger.error(error_message)
        raise ImportError(error_message) from e
