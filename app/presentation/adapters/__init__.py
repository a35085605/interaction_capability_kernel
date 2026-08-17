"""Optional application-presentation locator adapters."""

from app.presentation.adapters.capture import (
    FullCapturedFrameApplicationPresentationLocator,
)
from app.presentation.adapters.configured import (
    ConfiguredApplicationPresentationLocator,
)

__all__ = [
    "ConfiguredApplicationPresentationLocator",
    "FullCapturedFrameApplicationPresentationLocator",
]
