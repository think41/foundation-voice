"""
Text-to-Speech (TTS) provider module.
"""

import os
from typing import Dict, Any

from loguru import logger
from foundation_voice.utils.api_utils import _raise_missing_api_key
from foundation_voice.utils.provider_utils import import_provider_service
from dotenv import load_dotenv

load_dotenv()


def _create_cartesia_tts_service(tts_config: Dict[str, Any]) -> Any:
    CartesiaTTSService = import_provider_service(
        "pipecat.services.cartesia.tts", "CartesiaTTSService", "cartesia"
    )
    api_key = os.getenv("CARTESIA_API_KEY") or _raise_missing_api_key(
        "Cartesia", "CARTESIA_API_KEY"
    )
    return CartesiaTTSService(
        api_key=api_key,
        voice_id=tts_config.get("voice", "71a7ad14-091c-4e8e-a314-022ece01c121"),
    )


def _create_openai_tts_service(tts_config: Dict[str, Any]) -> Any:
    OpenAITTSService = import_provider_service(
        "pipecat.services.openai.tts", "OpenAITTSService", "openai"
    )
    api_key = os.getenv("OPENAI_API_KEY") or _raise_missing_api_key(
        "OpenAI TTS", "OPENAI_API_KEY"
    )
    return OpenAITTSService(
        api_key=api_key,
        voice=tts_config.get("voice", "alloy"),
    )


def _create_deepgram_tts_service(tts_config: Dict[str, Any]) -> Any:
    DeepgramTTSService = import_provider_service(
        "pipecat.services.deepgram.tts", "DeepgramTTSService", "deepgram"
    )
    api_key = os.getenv("DEEPGRAM_API_KEY") or _raise_missing_api_key(
        "Deepgram TTS", "DEEPGRAM_API_KEY"
    )
    return DeepgramTTSService(
        api_key=api_key,
        model=tts_config.get("model", "aura-asteria-en"),
        encoding=tts_config.get("encoding", "linear16"),
        container=tts_config.get("container", "none"),
        sample_rate=tts_config.get("sample_rate", 24000),
        chunk_size=tts_config.get("chunk_size", 1024),
    )


def _create_smallestai_tts_service(tts_config: Dict[str, Any]) -> Any:
    SmallestTTSService = import_provider_service(
        "foundation_voice.custom_plugins.services.smallest.tts",
        "SmallestTTSService",
        "smallestai",
    )
    api_key = os.getenv("SMALLESTAI_API_KEY") or _raise_missing_api_key(
        "SmallestAI TTS", "SMALLEST_AI_API_KEY"
    )
    return SmallestTTSService(
        api_key=api_key,
        model=tts_config.get("model", "lightning-v2"),  # Retain original default
        voice_id=tts_config.get("voice_id", None),
        speed=float(tts_config.get("speed", 1.0)),
    )


def _create_elevenlabs_tts_service(tts_config: Dict[str, Any]) -> Any:
    ElevenLabsTTSService = import_provider_service(
        "pipecat.services.elevenlabs.tts", "ElevenLabsTTSService", "elevenlabs"
    )
    api_key = os.getenv("ELEVENLABS_API_KEY") or _raise_missing_api_key(
        "ElevenLabs TTS", "ELEVENLABS_API_KEY"
    )
    return ElevenLabsTTSService(
        api_key=api_key,
        voice_id=tts_config.get(
            "voice_id", "YOUR_DEFAULT_ELEVENLABS_VOICE_ID"
        ),  # Recommended: Configure this in your agent_config.json
        model=tts_config.get("model", "eleven_turbo_v2"),
    )


def create_tts_service(tts_config: Dict[str, Any]) -> Any:
    """
    Create a TTS service based on configuration.

    Args:
        tts_config: Dictionary containing TTS configuration

    Returns:
        TTS service instance
    """
    tts_provider = tts_config.get("provider", "cartesia")  # Default provider

    # Dictionary mapping providers to their service creation helper functions
    tts_provider_factories = {
        "cartesia": _create_cartesia_tts_service,
        "openai": _create_openai_tts_service,
        "deepgram": _create_deepgram_tts_service,
        "smallestai": _create_smallestai_tts_service,
        "elevenlabs": _create_elevenlabs_tts_service,
    }

    # Get the factory function for the selected provider
    # If the provider is not found, default to cartesia's factory as per original logic
    provider_factory = tts_provider_factories.get(
        tts_provider, _create_cartesia_tts_service
    )

    logger.debug(f"Creating TTS service with provider: {tts_provider}")
    return provider_factory(tts_config)
