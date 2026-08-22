# 01 — Adopt Pydantic; convert package dataclasses to Pydantic models

Status: open
Type: task
Blocked by: (none)
Parent PRD: ../PRD.md

## Goal

Establish Pydantic as the project's standard for serialization/validation, and
convert the existing dataclasses in `src/basement_analysis/` to Pydantic models.
This is a foundational, self-contained refactor so later tickets build on
Pydantic from the start.

## Owner decision (verbatim)

> Switch all dataclasses to Pydantic models, use Pydantic for any new
> serialization/deserializations/validation from now on.

## Scope

- Add `pydantic` to `pyproject.toml` dependencies; `uv lock`.
- Convert existing dataclass record types (e.g. `Event`, `SensorReading`, and any
  other dataclasses in the package) to Pydantic models. Search the package for
  `@dataclass` and convert each.
- Keep behaviour identical — this ticket is a representation change only. `Event`
  gains its `event_type` enum in ticket 05, not here.
- Prefer frozen/immutable models (`model_config = ConfigDict(frozen=True)`) where
  the current dataclasses are frozen, to preserve semantics.

## Acceptance criteria

- No `@dataclass` record types remain in `src/basement_analysis/` (unless there's
  a documented reason a specific one can't be Pydantic).
- Full test suite green; `pyright` strict clean; `ruff` clean.
- No behavioural change to the build output.

## Notes

- Python 3.14, `typeCheckingMode = "strict"` — ensure Pydantic models type-check
  cleanly under pyright strict.
