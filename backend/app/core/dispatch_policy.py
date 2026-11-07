"""Explicit dispatch authorization policy boundary.

Enforces fail-closed protection at actual provider dispatch. Unapproved live
calls fail before any HTTP request or client creation, even when credentials
exist. Injected explicitly for mocked tests.
"""
from __future__ import annotations

from typing import Protocol


class LiveInferenceBlockedError(Exception):
    """Raised when live provider dispatch is attempted without authorization."""


class DispatchPolicy(Protocol):
    """Contract for authorizing provider dispatch."""

    can_dispatch: bool

    def check_dispatch(self, provider: str, model: str) -> None:
        """Raise LiveInferenceBlockedError if dispatch is unauthorized."""
        ...


class BlockedLiveDispatchPolicy:
    """Default fail-closed policy: rejects all live dispatches before HTTP."""

    can_dispatch: bool = False

    def check_dispatch(self, provider: str, model: str) -> None:
        raise LiveInferenceBlockedError(
            f"Live dispatch to provider '{provider}' (model '{model}') is blocked. "
            "Live calls remain unauthorized and paid budget is strictly $0."
        )


class MockDispatchPolicy:
    """Explicitly injected policy for offline tests using mocked transports."""

    can_dispatch: bool = True
    is_mock_only: bool = True

    def __init__(self, allowed_provider: str | None = None) -> None:
        self.allowed_provider = allowed_provider

    def check_dispatch(self, provider: str, model: str) -> None:
        if self.allowed_provider and provider != self.allowed_provider:
            raise LiveInferenceBlockedError(
                f"Mock dispatch not authorized for provider '{provider}'"
            )
        # Mock authorized
        return None
