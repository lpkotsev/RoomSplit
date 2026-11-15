from decimal import Decimal, InvalidOperation


CENT = Decimal("0.01")


def parse_amount(value: str) -> Decimal | None:
    if not value:
        return None

    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount.as_tuple().exponent < -2:
        return None

    try:
        return amount.quantize(CENT)
    except InvalidOperation:
        return None
