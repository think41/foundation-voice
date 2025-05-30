"""
Configuration loader module for loading and parsing configuration files.
"""

import json
import os
from typing import Dict, Any

from loguru import logger


class ConfigLoader:
    """
    Configuration loader class for loading and parsing configuration files.
    """

    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.

        Args:
            config_path: Path to the configuration file

        Returns:
            Dictionary containing the configuration
        """
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            logger.info(f"Loading configuration from: {config_path}")
            with open(config_path, "r") as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
