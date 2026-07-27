"""Abstract base class for all guardians in the MetaGuardian system."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import GuardianResult, GuardianType


class BaseGuardian(ABC):
    """Abstract base class for all guardian modules."""

    @abstractmethod
    def check(self) -> GuardianResult:
        """Run the guardian check and return a result.

        Returns:
            GuardianResult: The result of the health check.
        """
        pass

    @abstractmethod
    def guardian_type(self) -> GuardianType:
        """Return the type of this guardian.

        Returns:
            GuardianType: The type of guardian this instance represents.
        """
        pass