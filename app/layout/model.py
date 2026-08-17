from __future__ import annotations

from enum import Enum


class LayoutScalingStability(str, Enum):
    """Strongest render-extent scaling family expected to preserve layout."""

    UNSTABLE = "unstable"
    ISOTROPIC = "isotropic"
    ANISOTROPIC = "anisotropic"


__all__ = ["LayoutScalingStability"]
