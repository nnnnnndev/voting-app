"""End-to-end test of the ad-hoc candidate photo upload path via TestClient."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app import vote_assets


def _client(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MIE_DEV_AUTH", "1")
    monkeypatch.chdir(tmp_path)  # so data/ goes here
    vote_assets.ASSETS_ROOT = tmp_path / "data" / "vote_assets"
    # Re-import main fresh under the new cwd.
    import importlib
    import app.main as main_mod
    importlib.reload(main_mod)
    return TestClient(main_mod.app)


def test_upload_photo_sticks(monkeypatch, tmp_path: Path):
    c = _client(monkeypatch, tmp_path)
    # Dev-login.
    r = c.post("/auth/dev-login",
               data={"name": "Tester", "oid": "oid-tester"},
               follow_redirects=False)
    assert r.status_code in (303, 307)

    # 1x1 PNG.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63f8cf0000030001012cdda93b0000000049454e44"
        "ae426082"
    )

    r = c.post(
        "/elections/new",
        data={
            "template_id": "custom_ranked",
            "title": "Photo upload test",
            "description": "",
            "extra_name_0": "Jane Test",
            "extra_rank_0": "Asst. Prof., External",
        },
        files={"extra_photo_0": ("jane.png", BytesIO(png), "image/png")},
        follow_redirects=False,
    )
    assert r.status_code in (303, 307), f"got {r.status_code}: {r.text[:200]}"
    location = r.headers["location"]
    vote_id = location.rsplit("/", 1)[-1]

    # The photo file should now exist on disk.
    folder = tmp_path / "data" / "vote_assets" / vote_id
    assert folder.exists(), f"no folder at {folder}"
    files = list(folder.iterdir())
    assert files, f"no files in {folder}"
    assert files[0].suffix == ".png"

    # And the election record should reference it.
    election_path = tmp_path / "data" / "elections" / f"{vote_id}.json"
    text = election_path.read_text()
    assert "Jane Test" in text
    assert ".png" in text
