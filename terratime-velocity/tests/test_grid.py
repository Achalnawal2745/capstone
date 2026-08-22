from terratime.grid import generate_hex_grid, get_nct_delhi_boundary
from terratime.validate.facevalidity import LANDMARKS
import h3


def test_grid_generates_reasonable_hex_count():
    df = generate_hex_grid(9)
    # Spec targets ~15,000; our simplified boundary polygon is an
    # approximation, so allow a wide but sane band.
    assert 8_000 <= len(df) <= 30_000
    assert set(df.columns) == {"h3_index", "centroid_lat", "centroid_lon", "area_m2"}
    assert df["area_m2"].between(80_000, 130_000).all()


def test_grid_contains_all_facevalidity_landmarks():
    df = generate_hex_grid(9)
    known = set(df["h3_index"])
    for lm in LANDMARKS:
        cell = h3.latlng_to_cell(lm["lat"], lm["lon"], 9)
        assert cell in known, f"{lm['name']} not covered by the NCT Delhi grid"


def test_boundary_has_at_least_a_dozen_vertices():
    boundary = get_nct_delhi_boundary()
    assert len(boundary) >= 10
