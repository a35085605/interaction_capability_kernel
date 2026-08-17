from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

import numpy as np
import numpy.typing as npt

from geometry.rect import Rect
from geometry.size import Size


ImagePixels: TypeAlias = npt.NDArray[np.uint8]


class PixelFormat(str, Enum):
    """Storage format required to interpret one raster's pixels."""

    GRAY8 = "gray8"
    BGR24 = "bgr24"
    BGRA32 = "bgra32"

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(np.uint8)

    @property
    def channel_count(self) -> int:
        if self is PixelFormat.GRAY8:
            return 1
        if self is PixelFormat.BGR24:
            return 3
        return 4

    @property
    def dimension_count(self) -> int:
        return 2 if self.channel_count == 1 else 3


class Interpolation(str, Enum):
    NEAREST = "nearest"
    LINEAR = "linear"
    CUBIC = "cubic"
    AREA = "area"


def _validate_pixels(
    pixels: object,
    *,
    pixel_format: PixelFormat,
) -> ImagePixels:
    if not isinstance(pixels, np.ndarray):
        raise TypeError("raster pixels must be a numpy array")
    if not isinstance(pixel_format, PixelFormat):
        raise TypeError("pixel_format must be PixelFormat")
    if pixels.dtype != pixel_format.dtype:
        raise TypeError(
            "raster pixel dtype must match pixel format: "
            f"expected {pixel_format.dtype}, got {pixels.dtype}"
        )
    if pixels.ndim != pixel_format.dimension_count:
        raise ValueError(
            "raster pixel dimensions must match pixel format: "
            f"expected {pixel_format.dimension_count}D, "
            f"got shape {pixels.shape}"
        )
    if pixels.shape[0] <= 0 or pixels.shape[1] <= 0:
        raise ValueError("raster width and height must be greater than zero")
    if (
        pixel_format.dimension_count == 3
        and pixels.shape[2] != pixel_format.channel_count
    ):
        raise ValueError(
            "raster channel count must match pixel format: "
            f"expected {pixel_format.channel_count}, "
            f"got {pixels.shape[2]}"
        )
    return pixels


def _freeze_owned_pixels(
    pixels: object,
    *,
    pixel_format: PixelFormat,
) -> ImagePixels:
    source = _validate_pixels(pixels, pixel_format=pixel_format)
    return np.frombuffer(
        source.tobytes(order="C"),
        dtype=pixel_format.dtype,
    ).reshape(source.shape)


def _slice_pixels(
    pixels: ImagePixels,
    *,
    bounds: Rect,
) -> ImagePixels:
    if pixels.ndim == 2:
        return pixels[
            bounds.top:bounds.bottom,
            bounds.left:bounds.right,
        ]
    return pixels[
        bounds.top:bounds.bottom,
        bounds.left:bounds.right,
        :,
    ]


@dataclass(frozen=True, slots=True, init=False, eq=False)
class _OwnedRasterStorage:
    pixels: ImagePixels = field(compare=False, hash=False, repr=False)
    pixel_format: PixelFormat

    def __init__(
        self,
        *,
        pixels: ImagePixels,
        pixel_format: PixelFormat,
    ) -> None:
        object.__setattr__(
            self,
            "pixels",
            _freeze_owned_pixels(
                pixels,
                pixel_format=pixel_format,
            ),
        )
        object.__setattr__(self, "pixel_format", pixel_format)


@dataclass(frozen=True, slots=True, init=False, eq=False)
class _RasterSliceStorage:
    backing: _OwnedRasterStorage = field(
        compare=False,
        hash=False,
        repr=False,
    )
    bounds_in_backing: Rect = field(
        compare=False,
        hash=False,
        repr=False,
    )
    pixels: ImagePixels = field(compare=False, hash=False, repr=False)

    def __init__(
        self,
        *,
        backing: _OwnedRasterStorage,
        bounds_in_backing: Rect,
    ) -> None:
        if not isinstance(backing, _OwnedRasterStorage):
            raise TypeError("backing must be owned raster storage")
        if not isinstance(bounds_in_backing, Rect):
            raise TypeError("bounds_in_backing must be Rect")

        backing_bounds = Rect(
            x=0,
            y=0,
            width=int(backing.pixels.shape[1]),
            height=int(backing.pixels.shape[0]),
        )
        if not backing_bounds.contains_rect(bounds_in_backing):
            raise ValueError(
                "slice bounds must be contained by backing image bounds"
            )

        pixels = _slice_pixels(
            backing.pixels,
            bounds=bounds_in_backing,
        )
        if not np.shares_memory(pixels, backing.pixels):
            raise RuntimeError(
                "slice pixels must share memory with backing image"
            )
        if pixels.flags.writeable:
            raise RuntimeError("slice pixels must be read-only")

        object.__setattr__(self, "backing", backing)
        object.__setattr__(
            self,
            "bounds_in_backing",
            bounds_in_backing,
        )
        object.__setattr__(self, "pixels", pixels)

    @property
    def pixel_format(self) -> PixelFormat:
        return self.backing.pixel_format


_RasterStorage: TypeAlias = _OwnedRasterStorage | _RasterSliceStorage


@dataclass(frozen=True, slots=True, init=False, eq=False)
class RasterImage:
    """Immutable logical raster with private storage and explicit format.

    A raster may own an independent contiguous buffer or share a read-only
    slice of another raster. That storage choice is deliberately hidden from
    consumers. Use ``materialize_image()`` when an independent contiguous
    lifetime is required.
    """

    _storage: _RasterStorage = field(
        compare=False,
        hash=False,
        repr=False,
    )

    def __init__(
        self,
        *,
        pixels: ImagePixels,
        pixel_format: PixelFormat,
    ) -> None:
        object.__setattr__(
            self,
            "_storage",
            _OwnedRasterStorage(
                pixels=pixels,
                pixel_format=pixel_format,
            ),
        )

    @classmethod
    def _from_storage(cls, storage: _RasterStorage) -> RasterImage:
        if not isinstance(storage, (_OwnedRasterStorage, _RasterSliceStorage)):
            raise TypeError("storage must be raster storage")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_storage", storage)
        return instance

    def _crop(self, *, bounds: Rect) -> RasterImage:
        if not isinstance(bounds, Rect):
            raise TypeError("bounds must be Rect")
        if not self.bounds.contains_rect(bounds):
            raise ValueError("bounds must be contained by source image")
        if bounds == self.bounds:
            return self

        storage = self._storage
        if isinstance(storage, _OwnedRasterStorage):
            backing = storage
            bounds_in_backing = bounds
        else:
            backing = storage.backing
            parent = storage.bounds_in_backing
            bounds_in_backing = bounds.translated(
                dx=parent.left,
                dy=parent.top,
            )

        return RasterImage._from_storage(
            _RasterSliceStorage(
                backing=backing,
                bounds_in_backing=bounds_in_backing,
            )
        )

    def _materialize(self) -> RasterImage:
        if isinstance(self._storage, _OwnedRasterStorage):
            return self
        return RasterImage(
            pixels=self.pixels,
            pixel_format=self.pixel_format,
        )

    @property
    def pixels(self) -> ImagePixels:
        return self._storage.pixels

    @property
    def pixel_format(self) -> PixelFormat:
        return self._storage.pixel_format

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def dtype(self) -> np.dtype:
        return self.pixels.dtype

    @property
    def channel_count(self) -> int:
        return self.pixel_format.channel_count

    @property
    def size(self) -> Size:
        return Size(width=self.width, height=self.height)

    @property
    def bounds(self) -> Rect:
        return Rect(x=0, y=0, width=self.width, height=self.height)

    @property
    def is_contiguous(self) -> bool:
        return bool(self.pixels.flags.c_contiguous)

    @property
    def is_materialized(self) -> bool:
        """Whether this raster owns independent contiguous storage."""

        return isinstance(self._storage, _OwnedRasterStorage)
