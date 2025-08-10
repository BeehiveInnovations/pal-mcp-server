"""OpenRouter model registry for managing model configurations and aliases."""

import logging
import os
from pathlib import Path
from typing import Optional

try:
    from importlib.resources import files
except ImportError:
    # Python < 3.9 fallback
    from importlib_resources import files

from utils.file_utils import read_json_file

from .base import (
    ModelCapabilities,
    ProviderType,
    create_temperature_constraint,
)


class OpenRouterModelRegistry:
    """Registry for managing OpenRouter model configurations and aliases."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the registry.

        Args:
            config_path: Path to config file. If None, uses default locations.
        """
        self.alias_map: dict[str, str] = {}  # alias -> model_name
        self.model_map: dict[str, ModelCapabilities] = {}  # model_name -> config

        # Determine config path and loading strategy
        self.use_resources = False
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
                # Try importlib.resources first (proper way for packaged environments)
                try:
                    # Test if we can access the config via resources
                    resource_path = files("providers") / "../conf/custom_models.json"
                    if hasattr(resource_path, "read_text"):
                        # Resource exists and is accessible
                        self.config_path = None
                        self.use_resources = True
                    else:
                        raise FileNotFoundError("Resource method not available")
                except Exception:
                    # Fall back to file system paths
                    potential_paths = [
                        Path(__file__).parent.parent / "conf" / "custom_models.json",  # Development
                        Path("conf/custom_models.json"),  # Working directory
                    ]

                    # Find first existing path
                    self.config_path = None
                    for path in potential_paths:
                        if path.exists():
                            self.config_path = path
                            break

                    # If none found, default to the first one for error reporting
                    if self.config_path is None:
                        self.config_path = potential_paths[0]

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

    def _read_config(self) -> list[ModelCapabilities]:
        """Read configuration from file or package resources.

        Returns:
            List of model configurations
        """
        try:
            if self.use_resources:
                # Use importlib.resources for packaged environments
                try:
                    resource_path = files("providers") / "../conf/custom_models.json"
                    if hasattr(resource_path, "read_text"):
                        # Python 3.9+
                        config_text = resource_path.read_text(encoding="utf-8")
                    else:
                        # Python 3.8 fallback
                        with resource_path.open("r", encoding="utf-8") as f:
                            config_text = f.read()

                    import json

                    data = json.loads(config_text)
                    logging.debug("Loaded OpenRouter config from package resources")
                except Exception as e:
                    logging.warning(f"Failed to load config from resources: {e}")
                    return []
            else:
                # Use file path loading
                if not self.config_path.exists():
                    logging.warning(f"OpenRouter model config not found at {self.config_path}")
                    return []

                # Use centralized JSON reading utility
                data = read_json_file(str(self.config_path))
                logging.debug(f"Loaded OpenRouter config from file: {self.config_path}")

            if data is None:
                location = "resources" if self.use_resources else str(self.config_path)
                raise ValueError(f"Could not read or parse JSON from {location}")

            # Parse models
            configs = []
            for model_data in data.get("models", []):
                # Create ModelCapabilities directly from JSON data
                # Handle temperature_constraint conversion
                temp_constraint_str = model_data.get("temperature_constraint")
                temp_constraint = create_temperature_constraint(temp_constraint_str or "range")

                # Set provider-specific defaults based on is_custom flag
                is_custom = model_data.get("is_custom", False)
                if is_custom:
                    model_data.setdefault("provider", ProviderType.CUSTOM)
                    model_data.setdefault("friendly_name", f"Custom ({model_data.get('model_name', 'Unknown')})")
                else:
                    model_data.setdefault("provider", ProviderType.OPENROUTER)
                    model_data.setdefault("friendly_name", f"OpenRouter ({model_data.get('model_name', 'Unknown')})")
                model_data["temperature_constraint"] = temp_constraint

                # Remove the string version of temperature_constraint before creating ModelCapabilities
                if "temperature_constraint" in model_data and isinstance(model_data["temperature_constraint"], str):
                    del model_data["temperature_constraint"]
                model_data["temperature_constraint"] = temp_constraint

                config = ModelCapabilities(**model_data)
                configs.append(config)

            return configs
        except ValueError:
            # Re-raise ValueError for specific config errors
            raise
        except Exception as e:
            location = "resources" if self.use_resources else str(self.config_path)
            raise ValueError(f"Error reading config from {location}: {e}")

    def _build_maps(self, configs: list[ModelCapabilities]) -> None:
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

    def resolve(self, name_or_alias: str) -> Optional[ModelCapabilities]:
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
        # Registry now returns ModelCapabilities directly
        return self.resolve(name_or_alias)

    def list_models(self) -> list[str]:
        """List all available model names."""
        return list(self.model_map.keys())

    def list_aliases(self) -> list[str]:
        """List all available aliases."""
        return list(self.alias_map.keys())
