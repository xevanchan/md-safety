"""Data model for a licensed inspection station."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Station:
    """One licensed station, cleaned for display.

    ``raw_name`` and ``raw_address`` keep the state's original spelling so a
    re-casing bug never loses information. Coordinates stay ``None`` until the
    geocode step fills them in.
    """

    id: int
    name: str
    address: str
    city: str
    state: str
    zip: str
    phone: str | None
    classes: tuple[str, ...]
    e_inspection: bool
    raw_name: str
    raw_address: str
    lat: float | None = None
    lon: float | None = None
    geocode_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["classes"] = list(self.classes)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Station:
        return cls(**{**data, "classes": tuple(data["classes"])})
