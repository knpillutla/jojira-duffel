# Agent Guidelines

## Code Design & Architecture Rules

- **Always Create Modular Code**: Design software in decoupled, single-responsibility modules and components with clear interfaces.
- **Always Create Reusable Code**: Write functions, classes, and utilities designed for maximum reusability across services, adapters, and tests.
- **Avoid Duplicate Code**: Always inspect existing modules and helper functions before implementation. Reuse pre-existing utilities, abstractions, and functions rather than re-creating duplicate or overlapping logic.

## Error Handling & Exception Policy

- **Explicit Error Reporting (No Silent Fallbacks)**: Do not automatically fall back to default data or swallow exceptions when an error occurs. Always surface and log the exact error and exception details so the user can take corrective actions and fix the underlying issue.

## Token Efficiency & Communication Policy

- **Minimize Input & Output Tokens**: Keep context, prompts, and responses extremely concise and focused. Avoid conversational filler, redundant context, or repeating existing code needlessly.
- **Omit Default Explanations**: Do not provide explanations, summaries, or conceptual walkthroughs of code changes unless explicitly requested by the user.
- **Concise Diffs & Outputs**: Provide minimal, targeted diffs and direct answers rather than dumping entire files or verbose logs.
- **Do Not Automatically Execute Scratchpad Scripts**: Avoid creating or executing scratchpad scripts automatically or speculatively unless explicitly requested by the user, to prevent unnecessary token consumption.
