"""
Text-to-Speech (TTS) provider module.
"""

import os
from typing import Dict, Any

from loguru import logger
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.deepgram.tts import DeepgramTTSService

from foundation_voice.custom_plugins.services.smallest.tts import SmallestTTSService


def create_tts_service(tts_config: Dict[str, Any]) -> Any:
    """
    Create a TTS service based on configuration.

    Args:
        tts_config: Dictionary containing TTS configuration

    Returns:
        TTS service instance
    """
    tts_provider = tts_config.get("provider", "cartesia")

    def _raise_missing_tts_api_key():
        raise ValueError(
            "Missing API key for TTS provider. Please set 'api_key' in the config or in the environment variable."
        )

    # Dictionary mapping providers to their service creation functions
    tts_providers = {
        "cartesia": lambda: CartesiaTTSService(
            api_key=tts_config.get("api_key")
            or os.getenv("CARTESIA_API_KEY")
            or _raise_missing_tts_api_key(),
            voice_id=tts_config.get("voice", "71a7ad14-091c-4e8e-a314-022ece01c121"),
        ),
        "openai": lambda: OpenAITTSService(
            api_key=tts_config.get("api_key")
            or os.getenv("OPENAI_API_KEY")
            or _raise_missing_tts_api_key(),
            voice=tts_config.get("voice", "alloy"),
        ),
        "deepgram": lambda: DeepgramTTSService(
            api_key=tts_config.get("api_key")
            or os.getenv("DEEPGRAM_API_KEY")
            or _raise_missing_tts_api_key(),
        ),
        "smallestai": lambda: SmallestTTSService(
            api_key=tts_config.get("api_key")
            or os.getenv("SMALLESTAI_API_KEY")
            or _raise_missing_tts_api_key(),
            model="lightning-v2",
            voice_id=tts_config.get("voice_id", None),
        )
    }

    # Get the provider function or default to cartesia
    provider_func = tts_providers.get(tts_provider, tts_providers["cartesia"])
    logger.debug(f"Creating TTS service with provider: {tts_provider}")
    return provider_func()
