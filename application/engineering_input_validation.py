"""Typed application boundary for rejected engineering inputs."""


class EngineeringInputValidationError(ValueError):
    """A committed input is well formed but outside the supported domain."""


__all__ = ["EngineeringInputValidationError"]
