# Phase 7 Acceptance and Evidence

This report uses synthetic test accounts and records only. RoomSplit does not
transfer money or persist account or expense data.

## Acceptance matrix

| Acceptance area | Evidence | Status |
|---|---|---|
| Registration and sign-in; room creation; password-protected room-code joining; administrator appointment and record permissions | `tests/test_phase7.py`, `tests/test_phase2.py`, `tests/test_record_permissions.py` | Covered by tests |
| Categories; equal and custom expenses; participant snapshots; cent-level share and payer reconciliation; authorized expense editing and deletion | `tests/test_phase7.py`, `tests/test_phase3.py`, `tests/test_phase4.py`, `tests/test_equal_optional_dates.py`, `tests/test_expense_editing.py` | Covered by tests |
| Repayments and resulting balances | `tests/test_phase7.py`, `tests/test_phase5.py`, `tests/test_repayment_settlement.py` | Covered by tests |
| Dashboard date filters, category totals, balances, and room access | `tests/test_phase7.py`, `tests/test_phase6.py` | Pass |
| Runtime-only data and invalidation of an old session in a fresh app runtime | `tests/test_phase7.py`, `tests/test_phase2.py` | Pass |
| Full regression suite at the Phase 7 review | `python -m unittest discover -s tests` — 56 tests passed | Historical result |
| Tracked-diff whitespace check | `git diff --check` — exit status 0 | Pass |
| Local secret handling | `.env` is ignored by `.gitignore`, not tracked, and not staged; its contents were not read | Pass |
| Browser screenshots | No screenshot files were present during this review; the walkthrough below is test-backed rather than a manual browser capture | Not captured |
| Repository reference | Git remote `origin` points to <https://github.com/lpkotsev/RoomSplit> | Present; no commit or publish performed |

Unresolved `OPEN` decisions outside the approved behavior remain unverified and
were not used to infer additional requirements.

## Synthetic walkthrough

The end-to-end test `PhaseSevenAcceptanceTests.test_synthetic_journey_from_registration_through_dashboard`
uses two synthetic members:

1. Register and sign in as the room owner, create a password-protected room,
   join as a second member using the room code and password, and appoint that
   member as administrator.
2. Create Food and Travel categories. Record a EUR 10.00 equal-split Food
   expense and a EUR 6.00 equal-split Travel expense, both paid by the owner.
3. Record a EUR 2.00 repayment from the administrator to the owner.
4. Open the dashboard for 2026-08-03 through 2026-08-06. The category totals
   are Food EUR 10.00 and Travel EUR 6.00; the owner is owed EUR 6.00 and the
   administrator owes EUR 6.00. The selected date bounds are inclusive.
5. Try room, expense, repayment, category, and dashboard paths as a
   nonmember; the protected requests are denied.
6. Create a fresh app runtime and reuse the prior session cookie. The new
   runtime has no accounts, rooms, or expenses, and the old session redirects
   to sign-in.

## Remaining visual evidence

For browser screenshots, run the app with synthetic data and capture:

1. The dashboard showing all dates, category totals, and member balances.
2. The same dashboard after applying a changed date range.

Use only synthetic account names and records. Do not include passwords,
session cookies, room passwords, or real personal/financial data in screenshots.
Screenshots are not included in this repository yet.
