"""
Voice Activity Detection (VAD) provider module.
"""

from typing import Dict, Any, Optional

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams


def create_vad_analyzer(vad_config: Dict[str, Any]) -> Optional[Any]:
    """
    Create a VAD analyzer based on configuration.

    Args:
        vad_config: Dictionary containing VAD configuration

    Returns:
        VAD analyzer instance or None
    """
    vad_provider = vad_config.get("provider", "silero")

    params_config = vad_config.get("params", {})
    vad_params = VADParams(**params_config) if params_config else VADParams()

    # Dictionary mapping providers to their analyzer creation functions
    vad_providers = {
        "silero": lambda: SileroVADAnalyzer(params=vad_params),
        # Add other VAD providers here as needed
        "none": lambda: None,
    }

    # Get the provider function or default to None
    provider_func = vad_providers.get(vad_provider.lower(), vad_providers["none"])
    logger.debug(f"Creating VAD analyzer with provider: {vad_provider}")
    return provider_func()
