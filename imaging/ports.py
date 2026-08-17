from __future__ import annotations

from typing import Protocol

from geometry.size import Size
from imaging.models import Interpolation, RasterImage


class ImageResizer(Protocol):
    """Resize one raster without assigning application-level meaning."""

    def resize(
        self,
        image: RasterImage,
        *,
        target_size: Size,
        interpolation: Interpolation,
    ) -> RasterImage:
        ...
