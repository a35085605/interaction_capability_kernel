from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from numbers import Integral, Real

from geometry import Size
from imaging import ImagePixels, PixelFormat, RasterImage
from capture.domain.source import CaptureSourceId


def _normalize_non_empty_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string, "
            f"got {type(value).__name__}"
        )

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")

    return normalized


def _normalize_optional_text(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _normalize_non_empty_text(value, field_name=field_name)


def _normalize_finite_real(
    value: object,
    *,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(
            f"{field_name} must be a real number, "
            f"got {type(value).__name__}"
        )

    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    return normalized


def _normalize_unit_value(
    value: object,
    *,
    field_name: str,
) -> float:
    normalized = _normalize_finite_real(
        value,
        field_name=field_name,
    )
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            f"{field_name} must be between 0 and 1, "
            f"got {normalized}"
        )
    return normalized


def _normalize_non_negative_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{field_name} must be an integer, "
            f"got {type(value).__name__}"
        )

    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return normalized


@dataclass(frozen=True, slots=True, order=True)
class FrameId:
    """Monotonic frame sequence number within one capture stream."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_non_negative_integer(
                self.value,
                field_name="frame id",
            ),
        )


@dataclass(frozen=True, slots=True, order=True)
class CaptureStreamId:
    """Identity of one uninterrupted capture session."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _normalize_non_empty_text(
                self.value,
                field_name="capture stream id",
            ),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class CaptureQuality:
    """Quality of the captured pixels, not operational target state."""

    usable: bool
    sharpness: float | None = None
    contaminated: bool = False
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.usable, bool):
            raise TypeError("capture usable must be bool")
        if not isinstance(self.contaminated, bool):
            raise TypeError("capture contaminated must be bool")

        sharpness = self.sharpness
        if sharpness is not None:
            sharpness = _normalize_unit_value(
                sharpness,
                field_name="capture sharpness",
            )
            object.__setattr__(self, "sharpness", sharpness)

        object.__setattr__(
            self,
            "detail",
            _normalize_optional_text(
                self.detail,
                field_name="capture quality detail",
            ),
        )


@dataclass(frozen=True, slots=True)
class FrameInfo:
    """Immutable capture-local metadata for one acquired frame."""

    frame_id: FrameId
    stream_id: CaptureStreamId
    captured_at: datetime
    size: Size
    capture_backend_id: str
    source_id: CaptureSourceId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, FrameId):
            raise TypeError("frame_id must be FrameId")
        if not isinstance(self.stream_id, CaptureStreamId):
            raise TypeError("stream_id must be CaptureStreamId")
        if not isinstance(self.captured_at, datetime):
            raise TypeError("captured_at must be datetime")
        if self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        if not isinstance(self.size, Size):
            raise TypeError("size must be Size")
        if self.source_id is not None and not isinstance(self.source_id, CaptureSourceId):
            raise TypeError("source_id must be CaptureSourceId or None")
        object.__setattr__(
            self,
            "capture_backend_id",
            _normalize_non_empty_text(
                self.capture_backend_id,
                field_name="capture backend",
            ),
        )


def _validate_frame_payload(
    *,
    info: object,
    image: object,
    quality: object,
    field_prefix: str,
) -> tuple[FrameInfo, RasterImage, CaptureQuality]:
    if not isinstance(info, FrameInfo):
        raise TypeError(f"{field_prefix} info must be FrameInfo")
    if not isinstance(image, RasterImage):
        raise TypeError(f"{field_prefix} image must be RasterImage")
    if not isinstance(quality, CaptureQuality):
        raise TypeError(f"{field_prefix} quality must be CaptureQuality")
    if image.width != info.size.width or image.height != info.size.height:
        raise ValueError(
            f"{field_prefix} image size must match frame size: "
            f"expected {info.size.width}x{info.size.height}, "
            f"got {image.width}x{image.height}"
        )
    return info, image, quality


@dataclass(frozen=True, slots=True)
class AcquiredFrame:
    """Backend frame before the capture ownership boundary is crossed."""

    info: FrameInfo
    image: RasterImage
    quality: CaptureQuality

    def __post_init__(self) -> None:
        _validate_frame_payload(
            info=self.info,
            image=self.image,
            quality=self.quality,
            field_prefix="acquired frame",
        )


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """One immutable logical raster observation and its capture-local context.

    The raster is not required to own independent contiguous storage. Capture
    preserves observation identity and immutable pixel semantics without forcing
    an eager full-frame copy. Consumers that require independent storage must
    materialize explicitly at their own lifetime boundary.
    """

    info: FrameInfo
    image: RasterImage
    quality: CaptureQuality

    def __post_init__(self) -> None:
        _validate_frame_payload(
            info=self.info,
            image=self.image,
            quality=self.quality,
            field_prefix="captured frame",
        )

    @property
    def pixels(self) -> ImagePixels:
        return self.image.pixels

    @property
    def pixel_format(self) -> PixelFormat:
        return self.image.pixel_format
