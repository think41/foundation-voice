"""
Voice Activity Detection (VAD) provider module.
"""

from typing import Dict, Any, Optional

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer


def create_vad_analyzer(vad_config: Dict[str, Any]) -> Optional[Any]:
    """
    Create a VAD analyzer based on configuration.

    Args:
        vad_config: Dictionary containing VAD configuration

    Returns:
        VAD analyzer instance or None
    """
    vad_provider = vad_config.get("provider", "silero")

    # Dictionary mapping providers to their analyzer creation functions
    vad_providers = {
        "silero": lambda: SileroVADAnalyzer(),
        # Add other VAD providers here as needed
        "none": lambda: None,
    }

    # Get the provider function or default to None
    provider_func = vad_providers.get(vad_provider, vad_providers["none"])
    logger.debug(f"Creating VAD analyzer with provider: {vad_provider}")
    return provider_func()
