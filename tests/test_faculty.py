from app.faculty import get_registry, RANK_TENURED, RANK_UNTENURED


def test_loads_all_faculty():
    r = get_registry()
    assert len(r.members) == 39


def test_jiménez_unicode():
    r = get_registry()
    names = [m.name for m in r.members]
    assert "Juan Jiménez" in names


def test_all_photos_match():
    r = get_registry()
    missing = [m.name for m in r.members if not m.photo]
    assert missing == [], f"unmatched: {missing}"


def test_photo_assignments_unique():
    r = get_registry()
    photos = [m.photo for m in r.members if m.photo]
    assert len(photos) == len(set(photos))


def test_specific_known_mappings():
    """Spot-check the matcher on cases that previously broke."""
    r = get_registry()
    expected = {
        "Yossi Chait": "yossi",
        "Chaitra Gopalappa": "chaitra",
        "Stephen S. Nonnenmann": "stephen-removebg",
        "Stephen de Bruyn Kops": "de_bruyn_kops_stephen",
        "Matthew Lackner": "MattLackner",
        "Sunandita Sarker": "SSarker",
    }
    for name, expected_stem in expected.items():
        m = next(x for x in r.members if x.name == name)
        assert m.photo and expected_stem.lower() in m.photo.lower(), \
            f"{name} matched {m.photo}, expected stem {expected_stem}"


def test_tenure_classification():
    r = get_registry()
    # If the production status sheet is loaded, Branlard is flagged untenured
    # via the Pre-tenure marker. If not loaded, he reads tenured by rank.
    branlard = next(m for m in r.members if m.name == "Emmanuel Branlard")
    if branlard.untenured_override is True:
        assert not branlard.is_tenured
        assert branlard.is_untenured
    else:
        assert branlard.is_tenured
    assert branlard.rank == "Associate Professor"

    asst = next(m for m in r.members if m.rank == "Assistant Professor")
    assert not asst.is_tenured
    assert asst.is_tenure_track

    lect = next(m for m in r.members if m.rank in ("Lecturer", "Senior Lecturer"))
    assert not lect.is_tenured
    assert not lect.is_tenure_track
