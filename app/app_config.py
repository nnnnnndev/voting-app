"""Loader for the department-customizable rules config.

Reads `config/rules.yaml` at startup and exposes the values used by the
status sheet loader, election templates, and branding. To adopt this app
for another department, edit `config/rules.yaml`. No Python changes
required for most adaptations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


@dataclass
class Branding:
    app_name: str = "Voting"
    primary_color: str = "#881c1c"
    footer_note: str = ""


@dataclass
class StatusDef:
    code: str
    label: str
    hard_exclude: bool
    aliases: list[str]


@dataclass
class TemplateDef:
    id: str
    label: str
    description: str
    ballot_type: str
    seats: int = 1
    max_ranks: int = 1
    candidate_filter: str = "none"
    quorum_fraction: float = 2 / 3
    require_quorum: bool = False


@dataclass
class AppConfig:
    branding: Branding
    ay_columns: list[str]
    statuses: dict[str, StatusDef]
    name_aliases: dict[str, str]
    templates: dict[str, TemplateDef]

    @property
    def status_labels(self) -> dict[str, str]:
        return {code: s.label for code, s in self.statuses.items()}

    @property
    def status_aliases(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for code, s in self.statuses.items():
            for a in s.aliases:
                out[a.lower()] = code
        return out

    @property
    def hard_excludes(self) -> set[str]:
        return {code for code, s in self.statuses.items() if s.hard_exclude}


def _coerce_template(tid: str, raw: dict[str, Any]) -> TemplateDef:
    return TemplateDef(
        id=tid,
        label=raw.get("label", tid),
        description=raw.get("description", ""),
        ballot_type=raw["ballot_type"],
        seats=raw.get("seats", 1),
        max_ranks=raw.get("max_ranks", 1),
        candidate_filter=raw.get("candidate_filter", "none"),
        quorum_fraction=raw.get("quorum_fraction", 2 / 3),
        require_quorum=raw.get("require_quorum", False),
    )


@lru_cache(maxsize=1)
def load() -> AppConfig:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {CONFIG_PATH}. "
            f"Copy config/rules.yaml.template to config/rules.yaml and edit."
        )
    with CONFIG_PATH.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    branding_raw = raw.get("branding", {}) or {}
    branding = Branding(
        app_name=branding_raw.get("app_name", "Voting"),
        primary_color=branding_raw.get("primary_color", "#881c1c"),
        footer_note=branding_raw.get("footer_note", ""),
    )

    statuses_raw = raw.get("statuses", {}) or {}
    statuses: dict[str, StatusDef] = {}
    for code, sdef in statuses_raw.items():
        statuses[code] = StatusDef(
            code=code,
            label=sdef.get("label", code),
            hard_exclude=bool(sdef.get("hard_exclude", False)),
            aliases=list(sdef.get("aliases", [])),
        )

    templates_raw = raw.get("templates", {}) or {}
    templates = {
        tid: _coerce_template(tid, tdef) for tid, tdef in templates_raw.items()
    }

    return AppConfig(
        branding=branding,
        ay_columns=list(raw.get("ay_columns", [])),
        statuses=statuses,
        name_aliases=dict(raw.get("name_aliases", {})),
        templates=templates,
    )


def reset_cache() -> None:
    load.cache_clear()
