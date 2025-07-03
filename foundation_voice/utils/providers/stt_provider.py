"""
Speech-to-Text (STT) provider module.
"""

import os
from typing import Dict, Any

from loguru import logger

from foundation_voice.utils.api_utils import _raise_missing_api_key
from foundation_voice.utils.provider_utils import import_provider_service
from dotenv import load_dotenv

load_dotenv()


def _create_deepgram_service(stt_config: Dict[str, Any]) -> Any:
    """Create a Deepgram STT service."""
    DeepgramSTTService = import_provider_service(
        "pipecat.services.deepgram.stt", "DeepgramSTTService", "deepgram"
    )
    from deepgram import LiveOptions

    return DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY")
        or _raise_missing_api_key("Deepgram STT", "DEEPGRAM_API_KEY"),
        live_options=LiveOptions(
            model=stt_config.get("model", "nova-2-general"),
            language=stt_config.get("language", "en-us"),
        ),
        audio_passthrough=stt_config.get("audio_passthrough", False),
    )


def _create_openai_service(stt_config: Dict[str, Any]) -> Any:
    """Create an OpenAI STT service."""
    OpenAISTTService = import_provider_service(
        "pipecat.services.openai.stt", "OpenAISTTService", "openai"
    )

    return OpenAISTTService(
        api_key=os.getenv("OPENAI_API_KEY")
        or _raise_missing_api_key("OpenAI STT", "OPENAI_API_KEY"),
        model=stt_config.get("model", "whisper-1"),
        language=stt_config.get("language"),
    )


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
    stt_provider_factories = {
        "deepgram": _create_deepgram_service,
        "openai": _create_openai_service,
    }

    # Get the factory function for the selected provider
    provider_factory = stt_provider_factories.get(stt_provider.lower())
    if provider_factory is None:
        raise ValueError(
            f"Unsupported STT provider: {stt_provider}. "
            f"Available providers: {', '.join(stt_provider_factories.keys())}"
        )

    logger.debug(f"Creating STT service with provider: {stt_provider}")
    return provider_factory(stt_config)
