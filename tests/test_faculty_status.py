"""Tests for the faculty status sheet loader and eligibility logic.

Builds a synthetic xlsx fixture and verifies the loader + Faculty
integration. Does NOT depend on the user's real faculty_status.xlsx.
"""
from pathlib import Path

import pytest
from openpyxl import Workbook

from app import faculty as fac
from app.faculty_status import (
    HARD_EXCLUDES, STATUS_ALIASES, load_sheet, FacultyStatusSheet,
)


def _make_sheet(path: Path, rows: list[list]) -> None:
    """rows[0] is header; subsequent rows are data."""
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_loader_basic(tmp_path: Path):
    p = tmp_path / "fs.xlsx"
    _make_sheet(p, [
        ["", "Name", "AY 22-23", "AY 23-24", "AY 24-25"],
        ["", "Erin Baker", "Served", "", "GPD"],
        ["Pre-tenure", "Gina Olson", "", "Non-voting", ""],
        ["", "Stephen S. Nonnenmann", "GPD", "GPD", "Sabbatical"],
    ])
    sheet = load_sheet(p)
    assert sheet.ays == ["AY 22-23", "AY 23-24", "AY 24-25"]
    assert sheet.active_ay == "AY 24-25"
    assert sheet.untenured["Gina Olson"] is True
    assert sheet.untenured.get("Erin Baker", False) is False
    erin = sheet.by_name["Erin Baker"]
    assert any(s.code == "SERVED" and s.ay == "AY 22-23" for s in erin)
    assert any(s.code == "GPD" and s.ay == "AY 24-25" for s in erin)


def test_loader_first_name_resolves(tmp_path: Path):
    p = tmp_path / "fs.xlsx"
    _make_sheet(p, [
        ["", "Name", "AY 24-25"],
        ["", "Erin", "Served"],          # first name only
        ["", "Steve dBK", "UPD"],        # alias for Stephen de Bruyn Kops
    ])
    known = {"Erin Baker", "Stephen de Bruyn Kops"}
    sheet = load_sheet(p, known_names=known)
    assert "Erin Baker" in sheet.by_name
    assert "Stephen de Bruyn Kops" in sheet.by_name


def test_loader_handles_tp_case_with_punctuation(tmp_path: Path):
    p = tmp_path / "fs.xlsx"
    _make_sheet(p, [
        ["", "Name", "AY 24-25"],
        ["", "Shannon Roberts", "T/P Case (?)"],
    ])
    sheet = load_sheet(p)
    statuses = sheet.by_name["Shannon Roberts"]
    assert len(statuses) == 1
    assert statuses[0].code == "TP_CASE"
    assert statuses[0].label == "T/P Case"


def test_loader_missing_file_is_safe(tmp_path: Path):
    sheet = load_sheet(tmp_path / "does_not_exist.xlsx")
    assert sheet.ays == []
    assert sheet.by_name == {}


def test_hard_excludes_match_legend():
    expected = {
        "ADMIN", "GPD", "UPD", "CPC_REP", "TP_CASE", "NA",
        "SABBATICAL", "NOT_YET_FACULTY", "FIRST_YEAR", "SPLIT_APPT",
    }
    assert HARD_EXCLUDES == expected


def test_status_aliases_cover_legend():
    """Every status word from the legend has an alias mapping."""
    must_resolve = [
        "admin", "gpd", "upd", "cpc rep", "t/p case", "n/a",
        "sabbatical", "not yet faculty", "first year", "split appt",
        "served", "non-voting", "alternate", "did not serve",
    ]
    for key in must_resolve:
        assert key in STATUS_ALIASES, f"missing alias: {key}"


def test_eligibility_via_registry(tmp_path: Path, monkeypatch):
    """End-to-end: registry with status sheet applied gives correct eligibility."""
    p = tmp_path / "fs.xlsx"
    _make_sheet(p, [
        ["", "Name", "AY 24-25"],
        ["", "Erin Baker", "GPD"],          # hard exclude
        ["", "Hari Balasubramanian", "Served"],  # informational only
        ["Pre-tenure", "Gina Olson", "First year"],  # hard exclude + untenured
    ])
    monkeypatch.setattr(fac, "_registry", None)
    import app.faculty_status as fs_mod
    monkeypatch.setattr(fs_mod, "SHEET_PATH", p)
    monkeypatch.setattr(fs_mod, "find_sheet_path", lambda root=None: p)

    reg = fac.FacultyRegistry.load(verbose=False)
    erin = next(m for m in reg.members if m.name == "Erin Baker")
    hari = next(m for m in reg.members if m.name == "Hari Balasubramanian")
    gina = next(m for m in reg.members if m.name == "Gina Olson")

    assert reg.active_ay == "AY 24-25"
    eligible, reason = reg.eligibility(erin.id, "AY 24-25")
    assert not eligible and reason == "GPD"
    eligible, reason = reg.eligibility(hari.id, "AY 24-25")
    assert eligible and reason == ""
    eligible, reason = reg.eligibility(gina.id, "AY 24-25")
    assert not eligible and reason == "First year"

    # Untenured override from sheet flips Gina out of the tenured pool.
    assert gina.is_untenured is True
    assert gina.is_tenured is False


def test_history_listing(tmp_path: Path, monkeypatch):
    p = tmp_path / "fs.xlsx"
    _make_sheet(p, [
        ["", "Name", "AY 21-22", "AY 22-23", "AY 23-24", "AY 24-25"],
        ["", "Stephen S. Nonnenmann", "GPD", "GPD", "GPD", "Sabbatical"],
    ])
    monkeypatch.setattr(fac, "_registry", None)
    import app.faculty_status as fs_mod
    monkeypatch.setattr(fs_mod, "SHEET_PATH", p)
    monkeypatch.setattr(fs_mod, "find_sheet_path", lambda root=None: p)
    reg = fac.FacultyRegistry.load(verbose=False)
    stephen = next(m for m in reg.members if m.name == "Stephen S. Nonnenmann")
    hist = reg.recent_statuses(stephen.id, n=4)
    labels = [e.display for e in hist]
    assert labels[0] == "Sabbatical AY 24-25"
    assert labels[-1] == "GPD AY 21-22"
