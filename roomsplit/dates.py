from datetime import date


def parse_optional_date(value: str) -> date:
    return date.fromisoformat(value) if value else date.today()
