# TechContinuum Lead Radar — Project Context

## What this is
An MVP that discovers, researches, and ranks B2B SaaS companies likely to
need external advisory for moving AI-enabled products from experimentation
to production. Built for TechContinuum, a two-person senior advisory firm.

## Full specification
The complete build spec lives at `docs/spec.md`. Always refer to it for
detailed requirements — this file only holds context that applies across
every session.

## Hard constraints (never violate, regardless of phase)
- Do not send emails or build outreach sequences.
- Do not scrape personal LinkedIn profiles.
- Do not retrieve phone numbers.
- Do not fetch contacts before a company passes human approval.
- Do not let an LLM compute the final lead score — scoring is deterministic
  Python only.
- Do not claim a company lacks something (e.g. "no evaluation framework")
  based only on absence of public evidence.

## Phase discipline
Work strictly one phase at a time, per `docs/spec.md` Section 20. Do not
begin the next phase until the current phase's tests pass
(`make lint`, `make typecheck`, `make test`, `make demo`). Each phase ends
with a git commit before moving on — treat that commit as a stable
checkpoint.

## Integration notes (resolved, do not re-investigate)
- Vibe Prospecting is available via the `vpai` CLI. Read its live tool
  schemas before first use of each tool — do not assume parameters.
- LLM provider for MVP is the Anthropic API (Claude) only. Do not wire up
  other providers yet; the abstraction layer should support them later.

## Engineering conventions
Python 3.12. Pydantic v2, SQLModel/SQLAlchemy, SQLite for MVP, Typer, Rich,
pytest, ruff, mypy. Single-user, CLI-first — do not introduce distributed
architecture. See `docs/spec.md` Section 22 for the full list.
