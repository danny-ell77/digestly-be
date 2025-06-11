import yaml
import logging
from typing import Dict, Any
from enum import Enum
from dataclasses import dataclass
from app.models import DigestMode

logger = logging.getLogger("digestly")


class VideoLength(Enum):
    SHORT = "short"  # 0-10 minutes
    MEDIUM = "medium"  # 10-30 minutes
    LONG = "long"  # 30-60 minutes
    VERY_LONG = "very_long"  # 60+ minutes


@dataclass
class ModelConfig:
    primary_model: str
    max_tokens: int
    temperature: float = 0.7


class ModelSelector:
    def __init__(self, config_path: str = "model_config.yaml"):
        """Initialize the model selector with configuration."""
        logger.info(f"Initializing ModelSelector with config path: {config_path}")
        self.config = self._load_config(config_path)
        logger.debug(f"Loaded configuration: {self.config}")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load the YAML configuration file."""
        try:
            logger.info(f"Attempting to load config from: {config_path}")
            with open(config_path, "r") as file:
                config = yaml.safe_load(file)
                logger.info("Successfully loaded configuration file")
                return config
        except FileNotFoundError:
            logger.warning(
                f"Config file not found at {config_path}, using default configuration"
            )
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config file: {str(e)}", exc_info=True)
            logger.info("Falling back to default configuration")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if YAML file is missing."""
        logger.info("Using default model configuration")
        return {
            "models": {
                "tldr": {
                    "short": "llama-3.1-8b-instant",
                    "medium": "gemma2-9b-it",
                    "long": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "very_long": "meta-llama/llama-4-scout-17b-16e-instruct",
                },
                "key_insights": {
                    "short": "gemma2-9b-it",
                    "medium": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "long": "llama-3.3-70b-versatile",
                    "very_long": "deepseek-r1-distill-llama-70b",
                },
                "comprehensive": {
                    "short": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "medium": "llama-3.3-70b-versatile",
                    "long": "llama-3.3-70b-versatile",
                    "very_long": "llama-3.3-70b-versatile",
                },
                "article": {
                    "short": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "medium": "llama-3.3-70b-versatile",
                    "long": "llama-3.3-70b-versatile",
                    "very_long": "llama-3.3-70b-versatile",
                },
                "custom": {
                    "short": "llama-3.1-8b-instant",
                    "medium": "llama-3.3-70b-versatile",
                    "long": "llama-3.3-70b-versatile",
                    "very_long": "llama-3.3-70b-versatile",
                },
            },
            "token_limits": {
                "tldr": {
                    "llama-3.1-8b-instant": 800,
                    "gemma2-9b-it": 1000,
                    "meta-llama/llama-4-scout-17b-16e-instruct": 1200,
                },
                "key_insights": {
                    "gemma2-9b-it": 2000,
                    "meta-llama/llama-4-scout-17b-16e-instruct": 2500,
                    "llama-3.3-70b-versatile": 3000,
                    "deepseek-r1-distill-llama-70b": 3500,
                },
                "comprehensive": {
                    "meta-llama/llama-4-scout-17b-16e-instruct": 4000,
                    "llama-3.3-70b-versatile": 4500,
                    "deepseek-r1-distill-llama-70b": 5000,
                },
                "article": {
                    "meta-llama/llama-4-scout-17b-16e-instruct": 6000,
                    "deepseek-r1-distill-llama-70b": 7000,
                },
                "custom": {
                    "llama-3.1-8b-instant": 800,
                    "llama-3.3-70b-versatile": 10000,
                },
            },
            "temperature_settings": {
                "tldr": 0.3,
                "key_insights": 0.5,
                "comprehensive": 0.7,
                "article": 0.8,
                "custom": 0.6,
            },
        }

    def _categorize_video_length(self, duration_minutes: float) -> VideoLength:
        """Categorize video length based on duration in minutes."""
        logger.debug(
            f"Categorizing video length for duration: {duration_minutes} minutes"
        )
        if duration_minutes <= 10:
            category = VideoLength.SHORT
        elif duration_minutes <= 30:
            category = VideoLength.MEDIUM
        elif duration_minutes <= 60:
            category = VideoLength.LONG
        else:
            category = VideoLength.VERY_LONG
        logger.info(f"Video categorized as: {category.value}")
        return category

    def get_model_config(self, mode: DigestMode, video_duration: float) -> ModelConfig:
        """
        Get the optimal model configuration for given video duration and mode.

        Args:
            video_duration: Video length in minutes
            mode: Digest mode (TLDR, KEY_INSIGHTS, etc.)
            fallback_tier: Which fallback chain to use ('fast', 'balanced', 'quality')

        Returns:
            ModelConfig object with primary model and fallbacks
        """
        logger.info(
            f"Getting model config for mode: {mode.value}, duration: {video_duration} minutes"
        )

        length_category = self._categorize_video_length(video_duration)
        logger.debug(f"Video length category: {length_category.value}")

        primary_model = self.config["models"][mode.value][length_category.value]
        logger.info(f"Selected primary model: {primary_model}")

        # Updated logic: token limits depend on both mode and model
        token_limits = self.config["token_limits"].get(mode.value, {})
        max_tokens = token_limits.get(primary_model)
        if max_tokens is None:
            logger.warning(
                f"No token limit found for mode '{mode.value}' and model '{primary_model}', using default 1000"
            )
            max_tokens = 1000
        temperature = self.config["temperature_settings"][mode.value]
        logger.debug(f"Token limit: {max_tokens}, Temperature: {temperature}")

        config = ModelConfig(
            primary_model=primary_model, max_tokens=max_tokens, temperature=temperature
        )
        logger.info(f"Final model configuration: {config}")
        return config

    def get_model_for_content_type(
        self, video_duration: float, mode: DigestMode, content_type: str = "general"
    ) -> str:
        """
        Get model with content-type awareness.

        Args:
            video_duration: Video length in minutes
            mode: Digest mode
            content_type: Type of content ('educational', 'entertainment', 'news', 'technical')
        """
        logger.info(
            f"Getting model for content type: {content_type}, mode: {mode.value}, duration: {video_duration} minutes"
        )

        base_config = self.get_model_config(mode, video_duration)
        logger.debug(f"Base model configuration: {base_config}")

        if content_type in ["educational", "technical"] and mode != DigestMode.TLDR:
            logger.info(
                f"Processing {content_type} content, checking for model upgrade"
            )
            if "deepseek-r1-distill-llama-70b" not in base_config.primary_model:
                if video_duration > 30:
                    logger.info(
                        "Upgrading to deepseek-r1-distill-llama-70b for complex content"
                    )
                    return "deepseek-r1-distill-llama-70b"
                else:
                    logger.debug("Video duration too short for model upgrade")

        logger.info(f"Using model: {base_config.primary_model}")
        return base_config.primary_model
