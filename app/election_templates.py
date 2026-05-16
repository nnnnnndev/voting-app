"""Election templates.

Templates are loaded from config/rules.yaml. A template pre-fills sensible
defaults so faculty can spin up a vote in two clicks.
"""
from __future__ import annotations

from . import app_config
from .faculty import get_registry


# Backward-compatible alias: the rest of the app references TEMPLATES as a
# dict. We compute it from the YAML config at import time and refresh on
# demand.
TEMPLATES: dict = {}


def _refresh() -> None:
    TEMPLATES.clear()
    TEMPLATES.update(app_config.load().templates)


_refresh()


def apply_candidate_filter(filter_id: str) -> list[str]:
    reg = get_registry()
    if filter_id == "tenured":
        return [m.id for m in reg.members if m.is_tenured]
    if filter_id == "untenured":
        return [m.id for m in reg.members if m.is_untenured]
    if filter_id == "tenure_track":
        return [m.id for m in reg.members if m.is_tenure_track]
    return [m.id for m in reg.members]
