# RoomSplit Implementation Plan

## Status and source of truth

This plan is for the local student demo. The requirements source of truth is [the project brief](./project-brief.md), alongside [Copilot instructions](../.github/copilot-instructions.md). Module boundaries in [the architecture draft](./architecture-draft.md) are proposals unless confirmed there or below.

This is a historical phase plan. Later approved changes in the project brief
supersede it: refunds have been removed, expenses support equal or custom splits,
expense and repayment dates are optional, and administrator and record-editing
permissions follow the current brief.

## Approved technical decisions

- Use Flask with Jinja templates.
- Use Flask’s signed session cookie; store only the user ID in the session.
- Use the `ROOMSPLIT_SECRET_KEY` environment variable as Flask’s session secret. During local development, load it from an untracked `.env` file and add `.env` to `.gitignore`.
- Commit a `.env.example` containing only a placeholder; never generate, print, or commit a real session secret.
- Use a separate test-only secret in tests.
- Plan `python-dotenv` as the dependency for loading `.env` during local development. Add it to the project dependency manifest during implementation; do not install it as part of this documentation change.
- Keep account records and password hashes in runtime-only storage; do not persist them.
- An app restart clears runtime data and ends sessions. A prior cookie must not authenticate a user after the in-memory account record has been cleared.
- Use synthetic demo users and records; do not move money or persist data.

The password-hashing method and password policy remain `OPEN`. Do not add a committed or source-controlled real secret.

## Delivery approach

- Keep responsibilities modular and testable within a small local application.
- Apply membership and role authorization to every room-scoped read and write.
- Separate request validation and presentation from balance calculations.
- Use `Decimal`, not binary floating point, for money.
- Treat the brief as the behavior contract. If a necessary behavior is `OPEN`, pause that behavior or test for clarification rather than choosing a default.
- Use synthetic data for demonstrations and assignment evidence.

## Dependency flow

`Flask/Jinja shell and runtime store → account identity and room access → validated expenses → split/balance calculations → repayments/refunds → authorized dashboard views → end-to-end verification`

Room authorization applies to room data throughout the app, not only to room entry. Dashboard values should be derived from the same validated records and calculations used by the rest of the app.

## Phase 0 — Establish scope and verification baseline

### Modules and responsibilities

- **Requirements/test map:** map each confirmed brief requirement to a planned behavior and verification.
- **Decision register:** retain all unresolved requirements as `OPEN` and note where they prevent reliable implementation or tests.
- **Synthetic fixtures policy:** ensure planned examples use fictional accounts and records.

### Dependencies

- None. The Flask/Jinja and session/runtime-data decisions above are approved.

### Acceptance criteria and tests

- Confirmed requirements are represented in the later phases.
- Remaining `OPEN` items are listed without assumed answers.
- No application tests are required in this planning phase.

### Assignment evidence

- Requirements-to-test matrix.
- List of confirmed scope, approved technical decisions, and remaining `OPEN` items.

### Risks and unresolved decisions

- User profiles/group size, additional membership permissions, chart details, and further acceptance criteria remain `OPEN`.
- The password-hashing method and password policy remain `OPEN`; implementation details depending on them require a decision.

## Phase 1 — App foundation

### Modules and responsibilities

- **Flask application shell:** local entry point, Flask configuration boundary, Jinja templates, and static assets.
- **Runtime storage boundary:** in-memory storage for application data, including account records and password hashes; no persistence.
- **Session configuration:** configure signed Flask sessions to store only the user ID; read `ROOMSPLIT_SECRET_KEY` from the local `.env` file and use a separate test-only secret.
- **Validation/error boundary:** common approach for clear input errors, without expanding unspecified validation rules.
- **Test foundation:** startup and runtime-storage lifecycle tests using synthetic data.

### Dependencies

- Phase 0 requirements/test baseline.
- Approved stack and session/runtime-data decisions listed above.

### Acceptance criteria and tests

- The Flask app starts locally and presents a readable Jinja-based shell.
- A startup test verifies app creation and a basic response.
- Runtime storage is cleared when the app process restarts; account records and password hashes are not persisted.
- The session payload contains only the user ID. `.env` is ignored, `.env.example` contains only a placeholder, and tests provide a separate test-only secret.
- After restart, a prior session cannot resolve to an account and does not authenticate the user.
- No real personal data or secrets are used in tests.

### Assignment evidence

- Screenshot of the initial local page.
- Startup and storage-lifecycle test results.
- Demonstration that app restart clears runtime records and requires sign-in again.

### Risks and unresolved decisions

- Do not use a committed fallback secret; local development loads the key from the untracked `.env` file.
- Do not add account persistence or other persistence for convenience; the approved requirement is runtime-only data.

## Phase 2 — Accounts, rooms, and access control

### Modules and responsibilities

- **Accounts and sign-in:** username/password account creation and sign-in; keep account records and password hashes in runtime-only storage.
- **Session identity:** resolve the current user from the user ID in the signed session; reject stale sessions whose account record is absent.
- **Rooms:** room creation and a creator-set room password; joining by room code plus password or invite link plus password.
- **Membership and roles:** room membership, creator-as-owner role, assignment of a separate administrator, and member leaving.
- **Authorization policy:** common checks for membership and confirmed role permissions on every room-scoped operation.

### Dependencies

- Phase 1 Flask shell, runtime storage, and session configuration.

### Acceptance criteria and tests

- A person can create an account and sign in with a username and password.
- Account records and password hashes exist only while the app runs.
- A room creator is its owner and can assign another member as administrator after room creation.
- A person can join with a room code and the creator-set password, or with an invite link and that password.
- A nonmember cannot access room data or perform room actions.
- Owner/administrator permissions match confirmed room-management and expense/repayment edit-delete requirements.
- A member can leave; later membership changes do not alter participation on expenses already recorded.
- On app restart, the account store is empty and an old session no longer authenticates.
- Tests cover anonymous users, nonmembers, ordinary members, the owner, and the administrator for confirmed operations.

### Assignment evidence

- Synthetic-user walkthrough covering registration, sign-in, room creation, both join paths, administrator assignment, and leaving.
- Test results for session invalidation and allowed/denied room access.

### Risks and unresolved decisions

- The password-hashing method and password policy remain `OPEN`.
- Username uniqueness, room-code generation, invite-link format/lifetime, and detailed credential-validation rules are unspecified.
- The timing/behavior for assigning an administrator when no other member has joined is unspecified.
- Other room membership and permission rules remain `OPEN`; do not infer permissions for unspecified actions.

## Phase 3 — Expense entry and categories

### Modules and responsibilities

- **Expense input:** capture item, amount, payer(s), category, user-selected date, and equal/custom split information.
- **Expense validation:** enforce confirmed cent precision and require payer contributions and custom shares to equal the expense total; return clear errors.
- **Expense records:** store validated details and a snapshot of room members who participate at the time of recording.
- **Categories:** support member-created custom spending categories without inventing unspecified constraints or permissions.

### Dependencies

- Phase 1 application and runtime storage.
- Phase 2 identity, room membership, and authorization policy.

### Acceptance criteria and tests

- A room member can add an expense with the required details in EUR.
- Each member of the room at entry time participates; later joins or leaves do not alter that recorded participant set.
- Multiple payer contributions are recorded and must total the expense amount.
- Custom shares must total the expense amount; invalid expense entries are rejected with a clear error.
- Members can create custom spending categories.
- Nonmembers cannot submit or view room expenses.
- Tests cover confirmed validation rules, payer/share total mismatch, and participant snapshots.

### Assignment evidence

- Synthetic expense-entry walkthrough showing required fields, date, category, split choice, multiple payers, and validation feedback.
- Focused test output for payer totals, custom-share totals, and participant snapshots.

### Risks and unresolved decisions

- Further expense and settlement rules and unspecified validation constraints remain `OPEN`.
- Category permissions, naming constraints, duplicate handling, and deletion behavior are unspecified.
- Do not add validation rules for unspecified cases without clarification.

## Phase 4 — Split and balance calculations

### Modules and responsibilities

- **Money validation:** use `Decimal` and enforce cent-level precision for stored expense totals and payer contributions.
- **Split calculator:** calculate equal/custom participant shares independently of request handling.
- **Balance calculator:** derive member positions from payer contributions and assigned shares, then provide “who owes whom” results.
- **Calculation tests:** assert reconciliation invariants and approved examples independently of the web UI.

### Dependencies

- Phase 3 validated expense, payer, and participant records.

### Acceptance criteria and tests

- All money calculations use `Decimal`, never binary floating point.
- Expense totals and payer contributions are stored to cents.
- Custom shares equal the expense total or are rejected.
- Equal splits round to cents and satisfy the approved example: €10.00 across three members results in €3.34 for the selected payer and €3.33 for each other member.
- Calculated shares reconcile with the expense total for confirmed cases.
- Payer contributions reconcile with the expense total.
- Balance examples reconcile payer advances against participant shares.
- Tests cover representative equal/custom and multiple-payer cases, using only confirmed validation behavior.

### Assignment evidence

- Calculation table for synthetic equal/custom/multiple-payer examples.
- Focused test results for cent reconciliation, balance invariants, and the approved €10.00 example.

### Risks and unresolved decisions

- General rounding when independently rounded shares exceed the total, multiple remainder cents, or exact half-cent ties remains `OPEN`.
- Net accounting for all payer/participant overlap cases may need clarification beyond the agreed example.
- Do not infer a rounding mode or assert edge cases not defined in the brief.
- Other expense and settlement rules remain `OPEN`.

## Phase 5 — Repayments and refunds

### Modules and responsibilities

- **Repayment records:** payer, recipient, amount, date, and optional note.
- **Repayment balance effect:** reduce the balance between the named payer and recipient and reject a repayment greater than the current balance.
- **Refund records:** support partial/full refunds, optional expense linkage, and payer amounts for partial refunds of multi-payer expenses.
- **Refund balance effect:** linked refunds reduce/reverse the original expense; unlinked refunds do not automatically change balances.
- **Record authorization:** any member may add repayments/refunds; owner/administrator edit-delete rules apply to expenses and repayments; a member may edit/delete only their own refund.

### Dependencies

- Phase 2 membership and authorization.
- Phase 3 expense records and payer attribution.
- Phase 4 balance calculations.

### Acceptance criteria and tests

- Any room member can add a repayment or refund.
- A repayment reduces the balance between its payer and recipient; an overpayment is rejected.
- A linked refund reduces or reverses its original expense; an unlinked refund does not automatically change balances.
- For a partial refund on a multi-payer expense, the person recording the refund chooses payer amounts.
- Only the owner/administrator can edit or delete expenses and repayments.
- A member can edit/delete only the refund they recorded.
- Tests cover before/after balances, overpayment rejection, linked/unlinked refund effects, multiple-payer refund input, and authorization denials.

### Assignment evidence

- Synthetic before/after balance examples for repayment, linked refund, and unlinked refund.
- Test results for overpayment rejection and role/record-owner edit-delete boundaries.

### Risks and unresolved decisions

- Refunds exceeding the remaining refundable amount, repeated partial refunds, payer-allocation reconciliation, and historical edits after repayments are not fully specified.
- Ask for decisions before implementing or asserting behavior for those cases.
- Other expense, refund, repayment, and settlement rules remain `OPEN`.

## Phase 6 — Dashboard and visualizations

### Modules and responsibilities

- **Authorized read models:** room-scoped data preparation after membership checks.
- **Category spending view:** aggregate recorded spending by category for the selected date range.
- **Member balance view:** present calculated balances for room members.
- **Accessible presentation:** readable labels and keyboard-friendly controls.

### Dependencies

- Phases 2–5 for access control, expenses/categories, calculations, and repayment/refund effects.

### Acceptance criteria and tests

- Members can view spending by category and balances between members.
- Both views support date-range filters.
- Displayed amounts derive from validated EUR records and the same balance calculations tested in earlier phases.
- Nonmembers cannot access visualizations or underlying room data.
- UI controls meet readable-label and keyboard-friendly expectations.
- Tests cover required views, date-range changes, and room access; compare aggregation with synthetic fixtures.

### Assignment evidence

- Screenshots of synthetic category spending and member balances.
- A second screenshot showing a changed date range.
- Relevant UI/access-control test results.

### Risks and unresolved decisions

- Chart designs and filters beyond date range remain `OPEN`.
- Date boundaries and whether repayment/refund dates affect each visualization are unspecified.
- Keep presentation minimal until these semantics are clarified.

## Phase 7 — End-to-end verification and assignment evidence

### Modules and responsibilities

- **Integration scenarios:** cross-module user journeys from sign-in through dashboard.
- **Regression suite:** focused unit, authorization, integration, and UI tests selected for the approved stack.
- **Evidence package:** synthetic-data screenshots, test results, and acceptance-criteria status.

### Dependencies

- Phases 1–6. Any behavior tested must have confirmed semantics.

### Acceptance criteria and tests

- A synthetic journey covers account creation/sign-in, room creation and password-protected joining, administrator assignment, expense entry, balance calculation, repayments/refunds, and visualizations.
- Nonmembers are denied room access throughout the tested paths.
- Shares and payer contributions reconcile; confirmed repayment/refund effects are visible; invalid entries fail clearly.
- App restart clears runtime data and ends authenticated sessions.
- The demo uses only synthetic users/records and does not transfer money or persist account data/password hashes.
- Run relevant tests and report actual checks/results.
- The final checklist distinguishes passed criteria from blocked or unverified `OPEN` items.

### Assignment evidence

- End-to-end test results from the selected local environment.
- Screenshots or a brief walkthrough using synthetic data.
- Acceptance-criteria matrix with evidence references and explicit `OPEN`/blocked labels.

### Risks and unresolved decisions

- Any `OPEN` decision affecting a tested path blocks a reliable pass/fail assertion for that behavior.
- Keep unresolved cases unverified or pause for clarification; never mask them with a default.

## Remaining `OPEN` decisions and gates

| Decision or unresolved area | Status | Planning impact |
|---|---|---|
| Password-hashing method and password policy | `OPEN` | Must be chosen before implementing password creation/verification details. |
| Username rules, invite-link/code details, and account validation constraints | `OPEN` | Blocks detailed validation and edge-case tests; implement confirmed behavior only. |
| Other room membership and permission rules | `OPEN` | Blocks behavior/tests for unspecified membership actions. |
| Expense validation and custom-category constraints | `OPEN` | Blocks assertions for unspecified invalid-input/category cases. |
| General rounding beyond the €10.00/three-member example | `OPEN` | Blocks reliable tests for half-cent ties and other remainder cases. |
| Refund edge cases and settlement interactions | `OPEN` | Blocks reliable handling/tests for cumulative, excessive, or historically interacting refunds/repayments. |
| Chart design and date-range semantics beyond stated filters | `OPEN` | Blocks detailed presentation and aggregation assertions for unspecified date boundaries or record types. |
| User profiles, expected group size, and additional acceptance criteria | `OPEN` | Does not block minimal confirmed flows unless scope expands to depend on them. |

No phase silently resolves an `OPEN` item. Independent confirmed work may proceed, but pause any behavior or test whose correctness depends on an unresolved decision.
