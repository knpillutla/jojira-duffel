# Agent Guidelines

## Code Design & Architecture Rules

- **Always Create Modular Code**: Design software in decoupled, single-responsibility modules and components with clear interfaces.
- **Always Create Reusable Code**: Write functions, classes, and utilities designed for maximum reusability across services, adapters, and tests.
- **Avoid Duplicate Code**: Always inspect existing modules and helper functions before implementation. Reuse pre-existing utilities, abstractions, and functions rather than re-creating duplicate or overlapping logic.

## Error Handling & Exception Policy

- **Explicit Error Reporting (No Silent Fallbacks)**: Do not automatically fall back to default data or swallow exceptions when an error occurs. Always surface and log the exact error and exception details so the user can take corrective actions and fix the underlying issue.
