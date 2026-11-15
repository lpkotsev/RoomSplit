# RoomSplit Architecture Draft

This draft proposes module responsibilities; the stack, session, and runtime-data decisions below are approved, while other architecture choices remain proposals. Confirmed requirements come from [the project brief](./project-brief.md). Decisions marked `OPEN` remain unresolved.

## Proposed module responsibilities

- **Accounts and sign-in:** Account registration and username/password sign-in; identify the current user for authorization checks.
- **Rooms, membership, and permissions:** Room creation and room access using the code or invite link together with the creator-set password; membership state; role and permission checks before room actions. The creator is the room owner and assigns a separate administrator after creating the room.
- **Expenses and categories:** Validate and record expense details, dates, currency, payer contributions, and categories; support custom categories.
- **Split and balance calculations:** Isolate equal/custom split arithmetic and member balance derivation. Use `Decimal` and cent-level validation. Round equal shares to cents and assign any remainder to a payer’s share. If there are multiple payers, the person recording the expense chooses the payer who receives the remainder. For example, a €10.00 equal split among three members gives the selected payer €3.34 and the other two members €3.33 each.
- **Repayments and refunds:** Record repayments and apply them to the payer-recipient balance. Record linked or unlinked refunds with the specified balance effects. Any member may edit or delete only the refund they recorded.
- **Data storage:** Keep all records in runtime-only memory, including account records and password hashes. Do not persist them. On app restart, the runtime data is cleared and previous sessions no longer resolve to an account.
- **Dashboard and charts:** Present room balances and spending by category, with date-range filters. Specific chart designs and other filters remain `OPEN`.
- **Tests:** Verify confirmed acceptance criteria, validation, access controls, calculation invariants, refund/repayment balance effects, and explicitly approved edge-case rules.

## Proposed data flow

1. A user signs in and requests an action for a room.
2. The room membership and permissions boundary verifies that the user may access that room and perform the action.
3. Expense, repayment, or refund input is validated before being recorded in the in-memory store.
4. Expense and split records are passed to the calculation responsibility to derive member balances; repayment and refund records affect balances according to confirmed rules.
5. The dashboard reads authorized room data and presents balances and category totals using the selected date range.
6. Tests exercise validation, permissions, data flow, and balance invariants without using real user or financial data.

## Approved local-demo stack and session behavior

- Use Flask with Jinja templates.
- Use Flask’s signed session cookie and store only the user ID in the session.
- Read the `ROOMSPLIT_SECRET_KEY` Flask session secret from an untracked `.env` file during local development. Add `.env` to `.gitignore`.
- Commit a `.env.example` containing only a placeholder value; never commit a real secret.
- Use a separate test-only secret in tests.
- Plan `python-dotenv` as the dependency for loading `.env` during local development; it has not been installed.
- Keep account records and password hashes in runtime-only storage; do not persist them.
- An app restart clears runtime data and ends sessions. A previous cookie must not authenticate a user when its account record is gone.

The specific password-hashing method and password policy remain `OPEN`. Other module and dependency choices in this draft are proposals unless confirmed by the brief or listed above as approved.

## Open decisions affecting architecture

- **Password handling details:** The password-hashing method and password policy remain `OPEN`; only runtime-only storage of password hashes is approved.
- **Other brief items:** Preserve all remaining `OPEN` items, including unspecified user profiles, additional room permissions, chart details, and further acceptance criteria.
