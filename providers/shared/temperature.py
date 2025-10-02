"""Helper types for validating model temperature parameters."""

from abc import ABC, abstractmethod
from typing import Optional

__all__ = [
    "TemperatureConstraint",
    "FixedTemperatureConstraint",
    "RangeTemperatureConstraint",
    "DiscreteTemperatureConstraint",
    "create_temperature_constraint",
]

# Common heuristics for determining temperature support when explicit
# capabilities are unavailable (e.g., custom/local models).
_TEMP_UNSUPPORTED_PATTERNS = {
    "o1",
    "o3",
    "o4",  # OpenAI O-series reasoning models
    "deepseek-reasoner",
    "deepseek-r1",
    "r1",  # DeepSeek reasoner variants
}

_TEMP_UNSUPPORTED_KEYWORDS = {
    "reasoner",  # Catch additional DeepSeek-style naming patterns
}


class TemperatureConstraint(ABC):
    """Contract for temperature validation used by `ModelCapabilities`.

    Concrete providers describe their temperature behaviour by creating
    subclasses that expose three operations:
    * `validate` – decide whether a requested temperature is acceptable.
    * `get_corrected_value` – coerce out-of-range values into a safe default.
    * `get_description` – provide a human readable error message for users.

    Providers call these hooks before sending traffic to the underlying API so
    that unsupported temperatures never reach the remote service.
    """

    @abstractmethod
    def validate(self, temperature: float) -> bool:
        """Return ``True`` when the temperature may be sent to the backend."""

    @abstractmethod
    def get_corrected_value(self, temperature: float) -> float:
        """Return a valid substitute for an out-of-range temperature."""

    @abstractmethod
    def get_description(self) -> str:
        """Describe the acceptable range to include in error messages."""

    @abstractmethod
    def get_default(self) -> float:
        """Return the default temperature for the model."""

    @staticmethod
    def infer_support(model_name: str) -> tuple[bool, str]:
        """Heuristically determine whether a model supports temperature."""

        model_lower = model_name.lower()

        for pattern in _TEMP_UNSUPPORTED_PATTERNS:
            conditions = (
                pattern == model_lower,
                model_lower.startswith(f"{pattern}-"),
                model_lower.startswith(f"openai/{pattern}"),
                model_lower.startswith(f"deepseek/{pattern}"),
                model_lower.endswith(f"-{pattern}"),
                f"/{pattern}" in model_lower,
                f"-{pattern}-" in model_lower,
            )
            if any(conditions):
                return False, f"detected pattern '{pattern}'"

        for keyword in _TEMP_UNSUPPORTED_KEYWORDS:
            if keyword in model_lower:
                return False, f"detected keyword '{keyword}'"

        return True, "default assumption for models without explicit metadata"

    @staticmethod
    def resolve_settings(
        model_name: str,
        constraint_hint: Optional[str] = None,
    ) -> tuple[bool, "TemperatureConstraint", str]:
        """Derive temperature support and constraint for a model.

        Args:
            model_name: Canonical model identifier or alias.
            constraint_hint: Optional configuration hint (``"fixed"``,
                ``"range"``, ``"discrete"``). When provided, the hint is
                honoured directly.

        Returns:
            Tuple ``(supports_temperature, constraint, diagnosis)`` describing
            whether temperature may be tuned, the constraint object that should
            be attached to :class:`ModelCapabilities`, and the reasoning behind
            the decision.
        """

        if constraint_hint:
            constraint = create_temperature_constraint(constraint_hint)
            supports_temperature = constraint_hint != "fixed"
            reason = f"constraint hint '{constraint_hint}'"
            return supports_temperature, constraint, reason

        supports_temperature, reason = TemperatureConstraint.infer_support(model_name)
        if supports_temperature:
            constraint: TemperatureConstraint = RangeTemperatureConstraint(0.0, 2.0, 0.7)
        else:
            constraint = FixedTemperatureConstraint(1.0)

        return supports_temperature, constraint, reason


class FixedTemperatureConstraint(TemperatureConstraint):
    """Constraint for models that enforce an exact temperature (for example O3)."""

    def __init__(self, value: float):
        self.value = value

    def validate(self, temperature: float) -> bool:
        return abs(temperature - self.value) < 1e-6  # Handle floating point precision

    def get_corrected_value(self, temperature: float) -> float:
        return self.value

    def get_description(self) -> str:
        return f"Only supports temperature={self.value}"

    def get_default(self) -> float:
        return self.value


class RangeTemperatureConstraint(TemperatureConstraint):
    """Constraint for providers that expose a continuous min/max temperature range."""

    def __init__(self, min_temp: float, max_temp: float, default: Optional[float] = None):
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.default_temp = default or (min_temp + max_temp) / 2

    def validate(self, temperature: float) -> bool:
        return self.min_temp <= temperature <= self.max_temp

    def get_corrected_value(self, temperature: float) -> float:
        return max(self.min_temp, min(self.max_temp, temperature))

    def get_description(self) -> str:
        return f"Supports temperature range [{self.min_temp}, {self.max_temp}]"

    def get_default(self) -> float:
        return self.default_temp


class DiscreteTemperatureConstraint(TemperatureConstraint):
    """Constraint for models that permit a discrete list of temperature values."""

    def __init__(self, allowed_values: list[float], default: Optional[float] = None):
        self.allowed_values = sorted(allowed_values)
        self.default_temp = default or allowed_values[len(allowed_values) // 2]

    def validate(self, temperature: float) -> bool:
        return any(abs(temperature - val) < 1e-6 for val in self.allowed_values)

    def get_corrected_value(self, temperature: float) -> float:
        return min(self.allowed_values, key=lambda x: abs(x - temperature))

    def get_description(self) -> str:
        return f"Supports temperatures: {self.allowed_values}"

    def get_default(self) -> float:
        return self.default_temp


def create_temperature_constraint(constraint_type: str) -> TemperatureConstraint:
    """Factory that yields the appropriate constraint for a model configuration.

    The JSON configuration stored in ``conf/custom_models.json`` references this
    helper via human-readable strings.  Providers feed those values into this
    function so that runtime logic can rely on strongly typed constraint
    objects.
    """

    if constraint_type == "fixed":
        # Fixed temperature models (O3/O4) only support temperature=1.0
        return FixedTemperatureConstraint(1.0)
    if constraint_type == "discrete":
        # For models with specific allowed values - using common OpenAI values as default
        return DiscreteTemperatureConstraint([0.0, 0.3, 0.7, 1.0, 1.5, 2.0], 0.3)
    # Default range constraint (for "range" or None)
    return RangeTemperatureConstraint(0.0, 2.0, 0.3)
