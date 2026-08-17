from __future__ import annotations

from geometry.rect import Rect
from imaging.models import RasterImage


def _validate_image(image: object) -> RasterImage:
    if not isinstance(image, RasterImage):
        raise TypeError("image must be RasterImage")
    return image


def materialize_image(image: RasterImage) -> RasterImage:
    """Return an independent contiguous raster when the source is borrowed.

    A raster that already owns its storage is returned unchanged. A logical
    crop is copied so the result no longer retains or shares memory with its
    backing raster.
    """

    return _validate_image(image)._materialize()


def crop_image(image: RasterImage, *, bounds: Rect) -> RasterImage:
    """Return a logical zero-copy crop using image-local coordinates.

    The result remains the public ``RasterImage`` type. Its private storage
    retains the owned backing buffer and nested crops are flattened onto that
    buffer. Call ``materialize_image()`` at a lifetime boundary that requires
    an independent contiguous raster.
    """

    return _validate_image(image)._crop(bounds=bounds)
