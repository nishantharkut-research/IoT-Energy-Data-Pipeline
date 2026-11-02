"""Framework-independent canonical event contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from .identity import SourceLocator, source_event_id

__all__ = [
    "CanonicalEvent",
    "CanonicalMeteredEntity",
    "MAX_INT64",
    "MIN_INT64",
    "MAX_SCALED_VALUE",
    "MIN_SCALED_VALUE",
    "SourceLocator",
    "canonicalize_time",
    "logical_measurement_key",
    "source_event_id",
    "to_scaled_int",
]

MIN_INT64, MAX_INT64 = -(2**63), 2**63 - 1
MAX_SCALED_VALUE = 10**38 - 1
MIN_SCALED_VALUE = -MAX_SCALED_VALUE


@dataclass(frozen=True)
class CanonicalMeteredEntity:
    entity_id: str
    type_uris: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalEvent:
    schema_version: str
    dataset_version: str
    source_variant: str
    source_event_id: str
    source_relative_path: str
    workbook_sheet: str
    source_row_number: int
    meter_id: str
    brick_entity_id: str | None
    brick_building_ids: tuple[str, ...]
    brick_zone_ids: tuple[str, ...]
    brick_metered_entities: tuple[CanonicalMeteredEntity, ...]
    brick_unit_uri: str | None
    brick_usage_type: str | None
    original_timestamp_text: str
    source_timezone: str
    event_time_utc: str
    original_numeric_text: str
    scaled_value: int
    decimal_scale: int
    measurement_kind: str
    unit: str
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["brick_building_ids"] = list(self.brick_building_ids)
        result["brick_zone_ids"] = list(self.brick_zone_ids)
        result["brick_metered_entities"] = [
            {
                "entity_id": entity.entity_id,
                "type_uris": list(entity.type_uris),
            }
            for entity in self.brick_metered_entities
        ]
        result["quality_flags"] = list(self.quality_flags)
        return result


def logical_measurement_key(meter_id: str, event_time_utc: datetime) -> str:
    if event_time_utc.tzinfo is None:
        raise ValueError("event_time_utc must be timezone-aware")
    return f"{meter_id}|{event_time_utc.astimezone(ZoneInfo('UTC')).isoformat()}"


def to_scaled_int(
    text: str, scale: int, *, bounds: tuple[int, int] = (MIN_INT64, MAX_INT64)
) -> int:
    """Scale exactly using decimal digits, independent of the Decimal context.

    The default retains the legacy int64 API. Canonical records explicitly use
    MIN_SCALED_VALUE/MAX_SCALED_VALUE, matching decimal128(38, 0).
    """
    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 0:
        raise ValueError("scale must be a non-negative integer")
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal value: {text!r}") from exc
    if not value.is_finite():
        raise ValueError("value cannot be represented at the requested scale")
    sign, digits, exponent = value.as_tuple()
    assert isinstance(exponent, int)
    shift = exponent + scale
    if not any(digits):
        result = 0
    else:
        if shift < 0:
            places = -shift
            if places >= len(digits) or any(digits[-places:]):
                raise ValueError("value cannot be represented at the requested scale")
            digits = digits[:-places]
            shift = 0
        # Reject huge exponents before constructing a huge power or integer.
        max_digits = len(str(max(abs(bounds[0]), abs(bounds[1]))))
        if len(digits) + shift > max_digits:
            raise OverflowError("scaled value exceeds configured integer bounds")
        coefficient = 0
        for digit in digits:
            coefficient = coefficient * 10 + digit
        result = (-1 if sign else 1) * coefficient * 10**shift
    if not bounds[0] <= result <= bounds[1]:
        raise OverflowError("scaled value exceeds configured integer bounds")
    return result


def canonicalize_time(text: str, source_zone: ZoneInfo) -> datetime:
    raw = str(text).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {text!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=source_zone)
    return parsed.astimezone(ZoneInfo("UTC"))
