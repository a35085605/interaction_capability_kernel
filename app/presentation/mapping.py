from __future__ import annotations

from dataclasses import dataclass, field

from app.presentation.model import ApplicationPresentation
from geometry import AxisAlignedTransform, Point, Rect


@dataclass(frozen=True, slots=True)
class ApplicationPresentationMapping:
    """Axis-aligned mapping between equally anchored presentations."""

    source: ApplicationPresentation
    target: ApplicationPresentation
    source_to_target: AxisAlignedTransform = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, ApplicationPresentation):
            raise TypeError("source must be ApplicationPresentation")
        if not isinstance(self.target, ApplicationPresentation):
            raise TypeError("target must be ApplicationPresentation")
        if self.source.anchor != self.target.anchor:
            raise ValueError(
                "presentation mapping requires the same correspondence anchor"
            )
        object.__setattr__(
            self,
            "source_to_target",
            AxisAlignedTransform.from_rects(
                self.source.bounds,
                self.target.bounds,
            ),
        )

    def map_point(self, point: Point) -> Point:
        if not isinstance(point, Point):
            raise TypeError("point must be Point")
        if not self.source.bounds.contains_point(point):
            raise ValueError("point must be inside source application presentation")
        return self.source_to_target.map_point(point)

    def map_rect(self, rect: Rect) -> Rect:
        if not isinstance(rect, Rect):
            raise TypeError("rect must be Rect")
        if not self.source.bounds.contains_rect(rect):
            raise ValueError("rect must be inside source application presentation")
        return self.source_to_target.map_rect_enclosing(rect)

    def inverse(self) -> ApplicationPresentationMapping:
        return ApplicationPresentationMapping(
            source=self.target,
            target=self.source,
        )


__all__ = ["ApplicationPresentationMapping"]
