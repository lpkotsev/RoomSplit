---
name: test-first-feature
description: 'Use when implementing a RoomSplit feature or module with a test-first workflow: acceptance criteria, failing test, smallest change, and verification.'
---

# Test-First Feature Workflow

Use this reusable workflow for a requested feature or module. Creating or invoking this skill does not itself authorize implementing a RoomSplit feature.

## Procedure

1. Read the relevant requirements and identify explicit acceptance criteria. Record unresolved requirements as `OPEN` and ask for clarification when they block a correct test or implementation.
2. Inspect relevant code and tests to follow existing project conventions and avoid unrelated changes.
3. Write a focused test for a confirmed acceptance criterion and run it to verify that it fails for the expected reason.
4. Implement the smallest change that satisfies the criterion without expanding scope.
5. Run the relevant tests and any required targeted checks.
6. Inspect the actual command output and results. Fix failures caused by the change; do not claim checks passed unless they did.
7. Summarize the implementation, tests run, results, and any remaining `OPEN` items.

Do not invent behavior to fill gaps in the requirements. Do not skip the failing-test step unless the user explicitly authorizes a different workflow.
