# RoomSplit Project Brief

## 1. Project purpose

RoomSplit is a small Python web app for recording shared group expenses and calculating member balances. It helps group members understand who owes whom.

The app records expenses and calculates balances. It does not move money.

The interface calls a shared room an **event**. Creating an event requires a
name and password. The app generates a unique random event hashcode (the room
code); members can join using that hashcode and password or the existing invite
link and password. Room terminology below describes the same shared space.

## 2. Intended users

- People who share expenses in a group.
- Members of a group room.

Specific user profiles, group types, and expected group size: **OPEN**

## 3. Main user journeys

1. A person creates an account and signs in with a username and password.
2. A person creates a room and sets its password, or joins an existing room using either:
   - a room code and the room password, or
   - an invite link and the room password.
3. The room creator is the room owner and can appoint any room member, including themselves, as administrator.
4. Room members record shared expenses, including what was bought, the amount, payer or payers, category, date, and split information.
5. Room members can record repayments.
6. Members view balances and spending visualizations.

An event provides separate Members, Expenses, Repayments, and Member Balances
pages. Administrator appointment is on the Members page. The event pages retain
navigation to the dashboard, expense entry, and repayment entry.

Further details of the expense-entry, balance-review, and visualization journeys: **OPEN**

## 4. Functional requirements

- People can create an account and sign in with a username and password.
- A signed-in person can create a room (event) with a name and password.
- A signed-in person can join a room with a room code and password, or an invite link and password.
- Room members can add expense and repayment records.
- Expense records include what was bought, the amount, payer or payers, category, date, and split information.
- The app calculates and displays which member owes whom.
- The app provides visualizations of group spending.
- Invalid expense entries are rejected with a clear error.
- The app does not move money.

Other functional requirements: **OPEN**

## 5. Expense and balance rules

- The app uses one fixed currency: EUR.
- Expense and repayment dates are optional; if left blank when a
  record is created or edited, the current local date is used.
- Every member of the room when an expense is recorded participates in that expense. Joining or leaving later does not change its participants.
- Expenses use either an equal split (the default) or a custom split.
  Custom shares and payer contributions are entered per participant; blank
  fields mean zero. Each set of amounts must add up to the expense total.
- Store expense totals and payer contributions to cents. Round each member’s share to the nearest cent.
- Assign any rounding remainder to the share of the payer who contributed the
  most. If the highest contributions are tied, the person recording the
  expense chooses among the tied payers, even when the initial split has no
  remainder. For example, when a €10.00 expense is split equally among three
  members, that payer's share becomes €3.34 and the other shares remain €3.33.
- An expense can have multiple payers. Record each payer’s contribution, and require the contributions to add up to the expense total.
- Repayments are recorded between members and reduce the balance between the named payer and recipient. Reject a repayment that exceeds the current balance.
- Each repayment records who paid, who received it, the amount, and the date. A note is optional.
- Expenses and repayments display the member who created each record.
- Editing an expense preserves its original participant snapshot. Reject an
  expense edit or deletion if it would make a recorded repayment exceed the
  revised balance.
Other expense, repayment, and settlement rules: **OPEN**

## 6. Room membership and permissions

- People can create or join a room. To join, they need either a room code and the password set by the creator, or an invite link and that password.
- The room creator is the room owner and can appoint any current room member,
  including themselves, as administrator.
- The administrator can edit or delete any expense or repayment. Other current
  members, including an owner who is not administrator, can edit or delete
  only records they created.
- The room owner or administrator manages room membership.
- Members can leave a room.

Other room membership and permission details: **OPEN**

## 7. Visualizations

- The app shows spending by category and balances between members.
- These visualizations support date-range filters.
- Members can create custom spending categories.
- Expense entry suggests built-in categories and categories previously used in
  the event by starting letters. A new category is added to that event when the
  expense is successfully recorded. Category suggestions are runtime-only.

Specific chart designs and other filters: **OPEN**

## 8. Testing and acceptance criteria

- People can create accounts and sign in with a username and password.
- A room creator can set a room password, is the room owner, and can appoint any
  current member, including themselves, as administrator.
- A person can join with a room code and password, or an invite link and password.
- Every room member can add an expense or repayment record.
- Expense fields cover the item, amount, payer or payers, category, date, and split information.
- Every member of the room at the time an expense is recorded participates in it; later membership changes do not alter its participants.
- Equal splits assign any cent remainder to the largest payer, with a choice
  among tied largest payers.
- Custom shares and payer contributions are non-negative cent amounts and each
  must add up to the expense total.
- Multiple-payer contributions must equal the expense total; invalid expense
  entries are rejected with a clear error.
- Repayments reduce the balance between the recorded payer and recipient; an overpayment is rejected.
- The app displays spending-by-category and member-balance visualizations with date-range filters.
- The app does not transfer money.
- The local demo uses readable labels and keyboard-friendly controls.
- Data only needs to last while the app is running.

Other specific test cases and acceptance thresholds: **OPEN**

## 9. Out of scope

- Moving money or processing payments.
- Recording or calculating refunds.

Other out-of-scope features: **OPEN**

## 10. Open decisions

- Specific user profiles, group types, and expected group size: **OPEN**
- Other room membership and permission details: **OPEN**
- Specific chart designs and filters beyond date range: **OPEN**
- Other expense, repayment, and settlement rules: **OPEN**
- Other functional requirements and acceptance criteria: **OPEN**
