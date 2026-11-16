# RoomSplit Architecture Draft

This draft proposes module responsibilities; the stack, session, and runtime-data decisions below are approved, while other architecture choices remain proposals. Confirmed requirements come from [the project brief](./project-brief.md). Decisions marked `OPEN` remain unresolved.

## Proposed module responsibilities

- **Accounts and sign-in:** Account registration and username/password sign-in; identify the current user for authorization checks.
- **Rooms, membership, and permissions:** Room creation and room access using the code or invite link together with the creator-set password; membership state; role and permission checks before room actions. The creator is the room owner and can appoint any current member, including themselves, as administrator. The administrator can manage any expense or repayment; other members can manage only records they created.
- **Event naming:** The interface calls rooms events. A room stores a required event name and retains its generated random code, presented as the event hashcode. Existing room routes and password-protected invite links remain in use.
- **Expenses and categories:** Validate and record expense details, dates, currency, payer contributions, and categories; support custom categories.
- **Split and balance calculations:** Expenses support equal or custom splits.
  Equal splits assign the cent remainder to the largest payer; the recorder
  chooses between tied largest payers. Custom shares total the expense amount.
  Expense edits preserve participant snapshots; edits and deletions that
  invalidate recorded repayments are rejected. Use `Decimal` and cent-level
  validation.
- **Dates:** Expense and repayment dates default to the current local date
  when left blank, including when an expense or repayment is edited.
- **Repayments:** Record repayments and apply them to the payer and recipient's
  member balances; no money is transferred.
- **Data storage:** Keep all records in runtime-only memory, including account records and password hashes. Do not persist them. On app restart, the runtime data is cleared and previous sessions no longer resolve to an account.
- **Dashboard and charts:** Present room balances and spending by category, with date-range filters. Specific chart designs and other filters remain `OPEN`.
- **Tests:** Verify confirmed acceptance criteria, validation, access controls, calculation invariants, repayment balance effects, and explicitly approved edge-case rules.

## Proposed data flow

1. A user signs in and requests an action for a room.
2. The room membership and permissions boundary verifies that the user may access that room and perform the action.
3. Expense or repayment input is validated before being recorded in the in-memory store.
4. Expense and split records are passed to the calculation responsibility to derive member balances; repayment records affect balances according to confirmed rules.
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
