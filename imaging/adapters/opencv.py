from __future__ import annotations

import cv2
import numpy as np

from geometry.size import Size
from imaging.models import Interpolation, RasterImage


_INTERPOLATION_FLAGS = {
    Interpolation.NEAREST: cv2.INTER_NEAREST,
    Interpolation.LINEAR: cv2.INTER_LINEAR,
    Interpolation.CUBIC: cv2.INTER_CUBIC,
    Interpolation.AREA: cv2.INTER_AREA,
}


class OpenCVImageResizer:
    """OpenCV implementation of the general image-resize capability."""

    def resize(
        self,
        image: RasterImage,
        *,
        target_size: Size,
        interpolation: Interpolation,
    ) -> RasterImage:
        if not isinstance(image, RasterImage):
            raise TypeError("image must be RasterImage")
        if not isinstance(target_size, Size):
            raise TypeError("target_size must be Size")
        if not isinstance(interpolation, Interpolation):
            raise TypeError("interpolation must be Interpolation")

        source = np.ascontiguousarray(image.pixels)
        resized = cv2.resize(
            source,
            dsize=(target_size.width, target_size.height),
            interpolation=_INTERPOLATION_FLAGS[interpolation],
        )
        if image.pixels.ndim == 3 and resized.ndim == 2:
            resized = resized[:, :, None]
        return RasterImage(
            pixels=resized,
            pixel_format=image.pixel_format,
        )
