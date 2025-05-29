"""
Speech-to-Text (STT) provider module.
"""

import os
from typing import Dict, Any

from loguru import logger
from pipecat.services.deepgram.stt import DeepgramSTTService


def create_stt_service(stt_config: Dict[str, Any]) -> Any:
    """
    Create an STT service based on configuration.

    Args:
        stt_config: Dictionary containing STT configuration

    Returns:
        STT service instance
    """
    stt_provider = stt_config.get("provider", "deepgram")
    # Dictionary mapping providers to their service creation functions
    stt_providers = {
        "deepgram": lambda: (
            (lambda api_key: DeepgramSTTService(api_key=api_key))(
                stt_config.get("api_key")
                or os.getenv("DEEPGRAM_API_KEY")
                or _raise_missing_stt_api_key()
            )
        ),
        # Add other STT providers here as needed
    }

    def _raise_missing_stt_api_key():
        raise ValueError(
            "Missing API key for STT provider. Please set 'api_key' in the config or the DEEPGRAM_API_KEY environment variable."
        )

    # Get the provider function or default to deepgram
    provider_func = stt_providers.get(stt_provider, stt_providers["deepgram"])
    logger.debug(f"Creating STT service with provider: {stt_provider}")
    return provider_func()
