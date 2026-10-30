from decimal import Decimal

import pytest

from apps.bookings.services import cancellation_amounts


@pytest.mark.parametrize(
    ("paid", "percentage", "expected_penalty", "expected_refund"),
    [
        ("700.00", "25.00", "175.00", "525.00"),
        ("120.00", "100.00", "120.00", "0.00"),
        ("99.99", "0.00", "0.00", "99.99"),
        # ROUND_HALF_UP: 10.05 % de 100 produce 10.05, sin perder centavos.
        ("100.00", "10.05", "10.05", "89.95"),
        # El tercer decimal cinco sube, regla comun para importes comerciales.
        ("1.00", "12.50", "0.13", "0.87"),
    ],
)
def test_calcula_penalizacion_y_reembolso(
    paid, percentage, expected_penalty, expected_refund
):
    penalty, refund = cancellation_amounts(
        paid_amount=Decimal(paid), penalty_percentage=Decimal(percentage)
    )

    assert penalty == Decimal(expected_penalty)
    assert refund == Decimal(expected_refund)
