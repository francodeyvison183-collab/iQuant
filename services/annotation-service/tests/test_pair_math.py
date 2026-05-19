from decimal import Decimal

import pytest

from iquant_domain.errors import ValidationError

from iquant_annotation_service.usecases.pair_math import compute_pair_return_pct


def test_compute_pair_return_pct_basic() -> None:
    r = compute_pair_return_pct(Decimal("10"), Decimal("12"))
    assert r == Decimal("0.2000000000")


def test_compute_pair_return_pct_negative() -> None:
    r = compute_pair_return_pct(Decimal("10"), Decimal("8"))
    assert r == Decimal("-0.2000000000")


def test_compute_pair_return_pct_zero_buy_raises() -> None:
    with pytest.raises(ValidationError):
        compute_pair_return_pct(Decimal("0"), Decimal("10"))
