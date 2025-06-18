"""OpenRouter model registry for managing model configurations and aliases."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from utils.file_utils import read_json_file

from .base import ModelCapabilities, ProviderType, RangeTemperatureConstraint


@dataclass
class OpenRouterModelConfig:
    """Configuration for an OpenRouter model."""

    model_name: str
    aliases: list[str] = field(default_factory=list)
    context_window: int = 32768  # Total context window size in tokens
    supports_extended_thinking: bool = False
    supports_system_prompts: bool = True
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_json_mode: bool = False
    supports_images: bool = False  # Whether model can process images
    max_image_size_mb: float = 0.0  # Maximum total size for all images in MB
    is_custom: bool = False  # True for models that should only be used with custom endpoints
    description: str = ""

    def to_capabilities(self) -> ModelCapabilities:
        """Convert to ModelCapabilities object."""
        return ModelCapabilities(
            provider=ProviderType.OPENROUTER,
            model_name=self.model_name,
            friendly_name="OpenRouter",
            context_window=self.context_window,
            supports_extended_thinking=self.supports_extended_thinking,
            supports_system_prompts=self.supports_system_prompts,
            supports_streaming=self.supports_streaming,
            supports_function_calling=self.supports_function_calling,
            supports_images=self.supports_images,
            max_image_size_mb=self.max_image_size_mb,
            temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 1.0),
        )


class OpenRouterModelRegistry:
    """Registry for managing OpenRouter model configurations and aliases."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the registry.

        Args:
            config_path: Path to config file. If None, uses default locations.
        """
        self.alias_map: dict[str, str] = {}  # alias -> model_name
        self.model_map: dict[str, OpenRouterModelConfig] = {}  # model_name -> config

        # Determine config path
        if config_path:
            # Direct config_path parameter
            self.config_path = Path(config_path)
        else:
            # Check environment variable first
            env_path = os.getenv("CUSTOM_MODELS_CONFIG_PATH")
            if env_path:
                # Environment variable path
                self.config_path = Path(env_path)
            else:
                # Default to conf/custom_models.json - use relative path from this file
                # This works in development environment
                self.config_path = Path(__file__).parent.parent / "conf" / "custom_models.json"

        # Load configuration
        self.reload()

    def reload(self) -> None:
        """Reload configuration from disk."""
        try:
            configs = self._read_config()
            self._build_maps(configs)
            caller_info = ""
            try:
                import inspect

                caller_frame = inspect.currentframe().f_back
                if caller_frame:
                    caller_name = caller_frame.f_code.co_name
                    caller_file = (
                        caller_frame.f_code.co_filename.split("/")[-1] if caller_frame.f_code.co_filename else "unknown"
                    )
                    # Look for tool context
                    while caller_frame:
                        frame_locals = caller_frame.f_locals
                        if "self" in frame_locals and hasattr(frame_locals["self"], "get_name"):
                            tool_name = frame_locals["self"].get_name()
                            caller_info = f" (called from {tool_name} tool)"
                            break
                        caller_frame = caller_frame.f_back
                    if not caller_info:
                        caller_info = f" (called from {caller_name} in {caller_file})"
            except Exception:
                # If frame inspection fails, just continue without caller info
                pass

            logging.debug(
                f"Loaded {len(self.model_map)} OpenRouter models with {len(self.alias_map)} aliases{caller_info}"
            )
        except ValueError as e:
            # Re-raise ValueError only for duplicate aliases (critical config errors)
            logging.error(f"Failed to load OpenRouter model configuration: {e}")
            # Initialize with empty maps on failure
            self.alias_map = {}
            self.model_map = {}
            if "Duplicate alias" in str(e):
                raise
        except Exception as e:
            logging.error(f"Failed to load OpenRouter model configuration: {e}")
            # Initialize with empty maps on failure
            self.alias_map = {}
            self.model_map = {}

    def _read_config(self) -> list[OpenRouterModelConfig]:
        """Read configuration from file.

        Returns:
            List of model configurations
        """
        if not self.config_path.exists():
            logging.warning(f"OpenRouter model config not found at {self.config_path}")
            return []

        try:
            # Use centralized JSON reading utility
            data = read_json_file(str(self.config_path))
            if data is None:
                raise ValueError(f"Could not read or parse JSON from {self.config_path}")

            # Parse models
            configs = []
            for model_data in data.get("models", []):
                config = OpenRouterModelConfig(**model_data)
                configs.append(config)

            return configs
        except ValueError:
            # Re-raise ValueError for specific config errors
            raise
        except Exception as e:
            raise ValueError(f"Error reading config from {self.config_path}: {e}")

    def _build_maps(self, configs: list[OpenRouterModelConfig]) -> None:
        """Build alias and model maps from configurations.

        Args:
            configs: List of model configurations
        """
        alias_map = {}
        model_map = {}

        for config in configs:
            # Add to model map
            model_map[config.model_name] = config

            # Add the model_name itself as an alias for case-insensitive lookup
            # But only if it's not already in the aliases list
            model_name_lower = config.model_name.lower()
            aliases_lower = [alias.lower() for alias in config.aliases]

            if model_name_lower not in aliases_lower:
                if model_name_lower in alias_map:
                    existing_model = alias_map[model_name_lower]
                    if existing_model != config.model_name:
                        raise ValueError(
                            f"Duplicate model name '{config.model_name}' (case-insensitive) found for models "
                            f"'{existing_model}' and '{config.model_name}'"
                        )
                else:
                    alias_map[model_name_lower] = config.model_name

            # Add aliases
            for alias in config.aliases:
                alias_lower = alias.lower()
                if alias_lower in alias_map:
                    existing_model = alias_map[alias_lower]
                    raise ValueError(
                        f"Duplicate alias '{alias}' found for models '{existing_model}' and '{config.model_name}'"
                    )
                alias_map[alias_lower] = config.model_name

        # Atomic update
        self.alias_map = alias_map
        self.model_map = model_map

    def resolve(self, name_or_alias: str) -> Optional[OpenRouterModelConfig]:
        """Resolve a model name or alias to configuration.

        Args:
            name_or_alias: Model name or alias to resolve

        Returns:
            Model configuration if found, None otherwise
        """
        # Try alias lookup (case-insensitive) - this now includes model names too
        alias_lower = name_or_alias.lower()
        if alias_lower in self.alias_map:
            model_name = self.alias_map[alias_lower]
            return self.model_map.get(model_name)

        return None

    def get_capabilities(self, name_or_alias: str) -> Optional[ModelCapabilities]:
        """Get model capabilities for a name or alias.

        Args:
            name_or_alias: Model name or alias

        Returns:
            ModelCapabilities if found, None otherwise
        """
        config = self.resolve(name_or_alias)
        if config:
            return config.to_capabilities()
        return None

    def list_models(self) -> list[str]:
        """List all available model names."""
        return list(self.model_map.keys())

    def list_aliases(self) -> list[str]:
        """List all available aliases."""
        return list(self.alias_map.keys())
