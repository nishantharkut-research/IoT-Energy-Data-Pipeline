from __future__ import annotations

from decimal import Decimal, Inexact, localcontext

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iot_energy_pipeline.contracts import MAX_INT64, MIN_INT64, to_scaled_int


@pytest.mark.parametrize("precision", [6, 28, 50])
@pytest.mark.parametrize(
    ("text", "scale", "expected"),
    [
        ("26724.7", 15, 26724700000000000000),
        (str(10**38 - 1), 0, 10**38 - 1),
        (str(-(10**38 - 1)), 0, -(10**38 - 1)),
        (
            "0.12345678901234567890123456789012345678",
            38,
            12345678901234567890123456789012345678,
        ),
        ("0E-10000000", 38, 0),
    ],
)
def test_wide_scaling_is_exact_independent_of_decimal_context(
    precision: int, text: str, scale: int, expected: int
) -> None:
    with localcontext() as context:
        context.prec = precision
        context.traps[Inexact] = True
        assert (
            to_scaled_int(text, scale, bounds=(-(10**38 - 1), 10**38 - 1)) == expected
        )


@pytest.mark.parametrize("text", [str(10**38), str(-(10**38)), "1E10000000"])
def test_wide_scaling_rejects_overflow(text: str) -> None:
    with pytest.raises(OverflowError):
        to_scaled_int(text, 0, bounds=(-(10**38 - 1), 10**38 - 1))


@pytest.mark.parametrize("text", ["1.00000000000000000000000000001", "1E-10000000"])
def test_default_scaling_never_rounds_fractional_values(text: str) -> None:
    with localcontext() as context:
        context.prec = 3
        with pytest.raises(ValueError):
            to_scaled_int(text, 0)


@given(
    coefficient=st.integers(min_value=-(10**12), max_value=10**12),
    scale=st.integers(min_value=0, max_value=9),
)
def test_scaled_integer_round_trip_is_exact(coefficient: int, scale: int) -> None:
    source = Decimal(coefficient).scaleb(-scale)
    text = format(source, "f")

    encoded = to_scaled_int(text, scale)

    assert Decimal(encoded).scaleb(-scale) == source


@pytest.mark.parametrize("scale", [-1, 1.5, True, "2"])
def test_scale_must_be_a_non_negative_integer(scale: object) -> None:
    with pytest.raises(ValueError):
        to_scaled_int("1", scale)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text,scale,expected",
    [
        (str(MIN_INT64), 0, MIN_INT64),
        (str(MAX_INT64), 0, MAX_INT64),
        ("1.2300", 4, 12300),
        ("1.2300", 2, 123),
        ("12E2", 1, 12000),
        ("-0.01", 2, -1),
    ],
)
def test_scaled_integer_boundaries(text: str, scale: int, expected: int) -> None:
    assert to_scaled_int(text, scale) == expected


@pytest.mark.parametrize(
    "text,scale",
    [
        (str(MIN_INT64 - 1), 0),
        (str(MAX_INT64 + 1), 0),
        ("1.001", 2),
        ("NaN", 0),
        ("Infinity", 0),
    ],
)
def test_unrepresentable_values_fail(text: str, scale: int) -> None:
    with pytest.raises((ValueError, OverflowError)):
        to_scaled_int(text, scale)
