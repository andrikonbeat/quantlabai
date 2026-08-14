"""Template Registry for Project Template Engine (REQ-22 extended).

Provides case-insensitive registration and resolution of campaign templates.
The registry stores ``TemplateDefinition`` instances keyed by lowercase name
so lookup is O(1) and case-insensitive per the spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Type


class DuplicateTemplateError(Exception):
    """Raised when a template is registered with a name that already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Template {name!r} is already registered")


@dataclass(frozen=True)
class TemplateDefinition:
    """Definition of a registered campaign template.

    Attributes:
        name: Unique template identifier (e.g. ``standard_research``).
        template_class: The ``CampaignTemplate`` subclass that builds the project.
        profile: Human-readable profile name (typically matches ``name``).
    """

    name: str
    template_class: Type["CampaignTemplate"]
    profile: str


class TemplateRegistry:
    """Case-insensitive template registry.

    Stores ``TemplateDefinition`` instances keyed by lowercase name so
    ``register`` rejects duplicates regardless of case and ``resolve``
    accepts any casing.
    """

    def __init__(self) -> None:
        self._registry: dict[str, TemplateDefinition] = {}

    def register(self, definition: TemplateDefinition) -> None:
        """Register a template definition.

        Args:
            definition: The template definition to register.

        Raises:
            DuplicateTemplateError: If a template with the same name (case-
                insensitive) is already registered.
        """
        key = definition.name.lower()
        if key in self._registry:
            raise DuplicateTemplateError(definition.name)
        self._registry[key] = definition

    def resolve(self, name: str) -> TemplateDefinition:
        """Resolve a template by name.

        Args:
            name: Template name (case-insensitive).

        Returns:
            The matching ``TemplateDefinition``.

        Raises:
            KeyError: If no template with that name is registered.
        """
        key = name.lower()
        if key not in self._registry:
            raise KeyError(f"No template registered with name {name!r}")
        return self._registry[key]

    def all_definitions(self) -> list[TemplateDefinition]:
        """Return all registered definitions in insertion order."""
        return list(self._registry.values())


# Global registry instance with built-in templates pre-registered.
registry = TemplateRegistry()
