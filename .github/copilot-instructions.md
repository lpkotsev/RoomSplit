# RoomSplit Copilot Instructions

## Project scope

RoomSplit is a local Python web app for recording shared expenses, calculating balances, and visualizing spending. It does not move money. Follow [the project brief](../docs/project-brief.md) as the requirements source of truth.

The brief specifies username-and-password accounts; rooms joined by room code plus room password or invite link plus room password; equal or custom expense splits; EUR; expense dates; multiple payers; repayments; refunds; category and balance visualizations with date filters; and data that only needs to last while the app runs.

The brief contains requirements marked `OPEN`. Preserve those markers and treat those decisions as unresolved. Do not silently choose defaults or turn proposals into requirements.

## Engineering practices

- Write modular, readable Python and keep responsibilities focused.
- Validate user input explicitly and return clear errors for invalid data.
- Use `Decimal`, never binary floating point, for money calculations. Validate cent precision and keep rounding behavior consistent with the brief. If an exact rounding or remainder rule is `OPEN`, do not guess; keep it open and ask before implementing behavior that depends on it.
- Check room membership and authorization before allowing access to room data or actions. Apply the brief's permissions, and do not infer missing permissions.
- Keep credentials, tokens, passwords, and other secrets out of source control. Use synthetic demo users and synthetic expense, repayment, and refund data only.
- Do not add application behavior that goes beyond confirmed requirements. Identify unresolved requirements as `OPEN`.
