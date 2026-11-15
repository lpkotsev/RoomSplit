# RoomSplit Project Brief

## 1. Project purpose

RoomSplit is a small Python web app for recording shared group expenses and calculating member balances. It helps group members understand who owes whom.

The app records expenses and calculates balances. It does not move money.

## 2. Intended users

- People who share expenses in a group.
- Members of a group room.

Specific user profiles, group types, and expected group size: **OPEN**

## 3. Main user journeys

1. A person creates an account and signs in with a username and password.
2. A person creates a room and sets its password, or joins an existing room using either:
   - a room code and the room password, or
   - an invite link and the room password.
3. The room creator is the room owner and assigns another member as administrator after creating the room.
4. Room members record shared expenses, including what was bought, the amount, payer or payers, category, date, and split information.
5. Room members can record repayments and refunds.
6. Members view balances and spending visualizations.

Further details of the expense-entry, balance-review, and visualization journeys: **OPEN**

## 4. Functional requirements

- People can create an account and sign in with a username and password.
- A signed-in person can create a room and set its password.
- A signed-in person can join a room with a room code and password, or an invite link and password.
- Room members can add expense, repayment, and refund records.
- Expense records include what was bought, the amount, payer or payers, category, date, and split information.
- The app calculates and displays which member owes whom.
- The app provides visualizations of group spending.
- Invalid expense entries are rejected with a clear error.
- The app does not move money.

Other functional requirements: **OPEN**

## 5. Expense and balance rules

- The app uses one fixed currency: EUR.
- An expense has a date selected by the user.
- Every member of the room when an expense is recorded participates in that expense. Joining or leaving later does not change its participants.
- Expenses can be split equally or by custom amounts.
- Store expense totals and payer contributions to cents. Round each member’s share to the nearest cent.
- Assign any rounding remainder to a payer’s share. If there are multiple payers, the person recording the expense chooses which payer receives the remainder. For example, when a €10.00 expense is split equally among three members, the shares are €3.33 each before the remainder; the selected payer’s share becomes €3.34, and the other shares remain €3.33.
- Custom shares must add up to the expense total; otherwise, reject the entry with a clear error.
- An expense can have multiple payers. Record each payer’s contribution, and require the contributions to add up to the expense total.
- Repayments are recorded between members and reduce the balance between the named payer and recipient. Reject a repayment that exceeds the current balance.
- Each repayment records who paid, who received it, the amount, and the date. A note is optional.
- Refunds can be partial or full. Any room member can record a refund.
- A refund linked to an original expense reduces or reverses that expense. An unlinked refund does not change balances automatically.
- For a partial refund on an expense with multiple payers, the person recording the refund chooses the payer amounts.

Other expense, refund, repayment, and settlement rules: **OPEN**

## 6. Room membership and permissions

- People can create or join a room. To join, they need either a room code and the password set by the creator, or an invite link and that password.
- The room creator is the room owner and assigns another member as administrator after creating the room.
- Only the room owner or administrator can edit or delete expenses and repayments.
- Any room member can edit or delete only the refund they recorded.
- The room owner or administrator manages room membership.
- Members can leave a room.

Other room membership and permission details: **OPEN**

## 7. Visualizations

- The app shows spending by category and balances between members.
- These visualizations support date-range filters.
- Members can create custom spending categories.

Specific chart designs and other filters: **OPEN**

## 8. Testing and acceptance criteria

- People can create accounts and sign in with a username and password.
- A room creator can set a room password, is the room owner, and can assign another member as administrator after room creation.
- A person can join with a room code and password, or an invite link and password.
- Every room member can add an expense or repayment record; every room member can record a refund.
- Expense fields cover the item, amount, payer or payers, category, date, and split information.
- Every member of the room at the time an expense is recorded participates in it; later membership changes do not alter its participants.
- Equal splits round each member’s share to the nearest cent, with any remainder added to the selected payer’s share (for example, €10.00 split among three members gives the selected payer €3.34 and the other two members €3.33 each).
- Custom shares and multiple-payer contributions must each equal the expense total; invalid expense entries are rejected with a clear error.
- Repayments reduce the balance between the recorded payer and recipient; an overpayment is rejected.
- Linked refunds reduce or reverse the original expense; unlinked refunds do not automatically change balances.
- Any member can edit or delete only the refund they recorded.
- The app displays spending-by-category and member-balance visualizations with date-range filters.
- The app does not transfer money.
- The local demo uses readable labels and keyboard-friendly controls.
- Data only needs to last while the app is running.

Other specific test cases and acceptance thresholds: **OPEN**

## 9. Out of scope

- Moving money or processing payments.

Other out-of-scope features: **OPEN**

## 10. Open decisions

- Specific user profiles, group types, and expected group size: **OPEN**
- Other room membership and permission details: **OPEN**
- Specific chart designs and filters beyond date range: **OPEN**
- Other expense, refund, repayment, and settlement rules: **OPEN**
- Other functional requirements and acceptance criteria: **OPEN**
