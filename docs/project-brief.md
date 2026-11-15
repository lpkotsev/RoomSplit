# RoomSplit Project Brief

## 1. Project purpose

RoomSplit is a small Python web app for recording shared group expenses and calculating member balances. It helps group members understand who owes whom.

The app records expenses and calculates balances. It does not move money. 

## 2. Intended users

- People who share expenses in a group.
- Members of a group room.

Specific user profiles, group types, and expected group size: **OPEN - ask me**

## 3. Main user journeys

1. A person signs in.
2. The person creates or joins a group room.
3. Room members record shared spending, including:
   - what was bought,
   - how much it cost,
   - who paid, and
   - a spending category.
4. The app calculates which member owes whom.
5. Members view visualizations of group spending.

The exact expense-entry, balance-review, and visualization journeys: **OPEN - ask me**

## 4. Functional requirements

- People can sign in.
- A signed-in person can create a group room.
- A signed-in person can join a group room.
- Room members can record shared spending.
- Each recorded expense includes what was bought, how much it cost, who paid, and a spending category.
- The app calculates which member owes whom.
- The app provides visualizations of group spending.
- The app does not move money.

People can create an account and sign in with a username and password.

People can join a room with a room code, invite link, or room password.

Invalid expense entries are rejected with a clear error.

Other functional requirements: **OPEN - ask me**

## 5. Expense and balance rules

The app uses recorded shared spending to calculate which member owes whom.

Expenses can be split equally or by custom amounts.

The local demo uses one fixed currency: EUR. Each expense includes a date chosen by the user.

The app keeps exact decimal amounts rather than rounding split results. Every room member participates in each expense.

An expense can have multiple payers.

Refunds are supported as separate records.

Recorded repayments reduce the outstanding balance automatically.

The app records repayments between members.

## 6. Room membership and permissions

People can create or join a group room. Room members can record shared spending and view the resulting group balances.

People can join a room with a room code, invite link, or room password.

Only the room owner or administrator can edit or delete expenses and repayments. The room owner or administrator manages room membership. Creating a room does not give the creator a special role.

Members can leave a room.

The room owner or administrator is assigned manually.

Other permission details: **OPEN - ask me**

## 7. Visualizations

The app includes visualizations of spending by category and balances between members.

The spending and balance visualizations support date-range filters.

Specific chart design and other filters: **OPEN - ask me**

## 8. Testing and acceptance criteria

- People can sign in.
- A person can create or join a group room.
- Every room member can add an expense or repayment record.
- Expense records provide fields for all required details: item, amount, payer or payers, category, date, and split information.
- The app calculates and displays which member owes whom according to the agreed expense and balance rules.
- The app displays visualizations of group spending.
- The app does not transfer money.

The target environment is a local demo. Data only needs to last while the app is running.

The local demo should use readable labels and keyboard-friendly controls.

The test suite should verify that every room member can add a record and that all required record details are represented by fields.

Other specific test cases and acceptance thresholds: **OPEN - ask me**

## 9. Out of scope

- Moving money or processing payments.

Other out-of-scope features: **OPEN - ask me**

## 10. Open decisions

- How people sign in: New people can create an account and sign in with a username and password.
- How people join a room: People use a room code or invite link.
- Whether expenses split equally, by custom amounts, or both: The app supports both equal splits and custom amounts.
- Whether the app records repayments: The app records repayments between members.
- What members can edit or delete: Only the room owner or administrator can edit or delete entries.
- Which charts and visualizations are useful: The app shows spending by category and balances between members, with date-range filters.
- Whether this is a local demo or intended for deployment: RoomSplit is intended as a local demo; data only needs to last while the app is running.
- Supported currencies and date handling: The local demo uses one fixed currency: EUR. Each expense includes a date chosen by the user.
- Expense validation and error handling: Invalid expense entries are rejected with a clear error.
- Rounding, partial participation, multiple payers, refunds, and settlement rules: The app keeps exact decimal amounts, every room member participates in each expense, an expense can have multiple payers, refunds are separate records, and repayments reduce the outstanding balance automatically.
- Room ownership, membership management, and leaving a room: The room owner or administrator manages membership, members can leave a room, creating a room does not give the creator a special role, and the owner or administrator is assigned manually.
- Accessibility and other acceptance criteria: The local demo should use readable labels and keyboard-friendly controls. Every room member can add a record, and records provide fields for all required details. Other acceptance criteria are **OPEN - ask me**.
