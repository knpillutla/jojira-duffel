# Agent Guidelines

## Code Design & Architecture Rules

- **Always Create Modular Code**: Design software in decoupled, single-responsibility modules and components with clear interfaces.
- **Strict File Size Limit (200-300 Lines Maximum)**: Never create or maintain code files exceeding 200–300 lines. If a file approaches or exceeds this limit, decompose it into focused, single-responsibility files and reusable submodules within the same package.
- **Always Create Reusable Code**: Write functions, classes, and utilities designed for maximum reusability across services, adapters, and tests.
- **Avoid Duplicate Code**: Always inspect existing modules and helper functions before implementation. Reuse pre-existing utilities, abstractions, and functions rather than re-creating duplicate or overlapping logic.

## Error Handling & Exception Policy

- **Explicit Error Reporting (No Silent Fallbacks)**: Do not automatically fall back to default data or swallow exceptions when an error occurs. Always surface and log the exact error and exception details so the user can take corrective actions and fix the underlying issue.

## Mandatory Database Schema Standards

- **Standard Audit & Test Mode Columns**: Every database table created in the system MUST include the following standard columns:
  1. `created_at` (TIMESTAMP / TEXT ISO-8601): Timestamp when the record was created (defaults to current date/time upon insertion).
  2. `created_by` (VARCHAR / TEXT): User ID or system process that created the record (defaults to active user ID or system service upon insertion).
  3. `updated_at` (TIMESTAMP / TEXT ISO-8601): Timestamp when the record was last updated (automatically set to current date/time on create and updated upon every record modification).
  4. `updated_by` (VARCHAR / TEXT): User ID or system process that modified the record (automatically set to active user ID on create and updated upon every record modification).
  5. `is_test` (BOOLEAN DEFAULT FALSE / INTEGER DEFAULT 0): Indicator flag used to identify test records for live production testing and troubleshooting.


## Command Execution Policy

- **Do Not Automatically Execute Commands**: Never automatically run shell/terminal commands, build scripts, deploy scripts, or scratchpad scripts unless explicitly requested by the user. Always show the command to the user or ask for confirmation first.

## Token Efficiency & Communication Policy


- **Minimize Input & Output Tokens**: Keep context, prompts, and responses extremely concise and focused. Avoid conversational filler, redundant context, or repeating existing code needlessly.
- **Omit Default Explanations**: Do not provide explanations, summaries, or conceptual walkthroughs of code changes unless explicitly requested by the user.
- **Concise Diffs & Outputs**: Provide minimal, targeted diffs and direct answers rather than dumping entire files or verbose logs.
- **Do Not Automatically Execute Commands**: Do not automatically run shell/terminal commands or scratchpad scripts unless explicitly requested by the user, to prevent unnecessary token consumption and unexpected execution.
