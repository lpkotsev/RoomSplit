---
name: expense-balances
description: 'Use when reasoning about RoomSplit expense splits, multiple payers, repayments, refunds, or member balances.'
---

# Expense and Balance Reasoning

Use this workflow when designing, implementing, or reviewing calculations that affect expense shares or member balances.

## Workflow

1. Read `docs/project-brief.md` and extract the confirmed rules relevant to the change.
2. Identify the participants, expense total, payer contributions, split method, repayment or refund records, and the intended balance effects.
3. Mark any unresolved rounding, remainder, allocation, or permission behavior as `OPEN`. Ask for a decision rather than guessing.
4. Use Python `Decimal` for all money arithmetic. Do not convert money to binary floating point.
5. Validate values at cent precision against the brief. Confirm that custom shares and payer contributions sum to the required total where specified. Reject invalid input with a clear error.
6. Define and test balance invariants, such as:
   - expense shares sum to the expense total,
   - payer contributions sum to the expense total,
   - repayments update only the balance between the named payer and recipient,
   - linked refunds affect the linked expense as specified, and unlinked refunds do not automatically change balances.
7. Add or update focused tests for valid, invalid, boundary, and multi-member cases, including any approved rounding/remainder behavior.
8. Summarize the rules applied, tests run and their results, and remaining `OPEN` questions.

Do not treat example calculations as permission to decide behavior that the brief still marks `OPEN`.
