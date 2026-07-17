"""run_summary.md writer. Spec §15."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from lead_radar.settings import REPO_ROOT

TEMPLATES_DIR = REPO_ROOT / "templates"


class RunSummary(BaseModel):
    run_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider_name: str

    accounts_discovered: int
    accounts_rejected_by_hard_gates: int
    accounts_researched: int

    classification_counts: dict[str, int] = Field(default_factory=dict)

    estimated_credits_used: float = 0.0
    actual_credits_used: float = 0.0

    provider_errors: list[str] = Field(default_factory=list)
    top_signals: list[tuple[str, int]] = Field(default_factory=list)
    top_pain_tracks: list[tuple[str, int]] = Field(default_factory=list)
    research_gaps: list[str] = Field(default_factory=list)


def render_run_summary(summary: RunSummary) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("run_summary.md.j2")
    return template.render(summary=summary)


def write_run_summary(summary: RunSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_run_summary(summary), encoding="utf-8")
