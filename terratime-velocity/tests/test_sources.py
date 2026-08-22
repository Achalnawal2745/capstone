import pandas as pd
import pytest

from terratime.sources.base import OBSERVATION_COLUMNS, validate_observations_schema
from terratime.sources.earthengine import EarthEngineSource
from terratime.sources.synthetic import SyntheticSource


def test_synthetic_source_emits_canonical_schema():
    source = SyntheticSource(year_start=2016, year_end=2020, n_hexes=15, seed=1)
    df = source.load_observations()

    assert set(OBSERVATION_COLUMNS) <= set(df.columns)
    validate_observations_schema(df)  # must not raise
    assert df["h3_index"].nunique() == 15
    assert sorted(df["year"].unique()) == list(range(2016, 2021))
    assert df["built_frac_soft"].between(0, 1).all()
    assert df["built_frac_hard"].between(0, 1).all()


def test_synthetic_source_is_deterministic_given_seed():
    a = SyntheticSource(year_start=2016, year_end=2020, n_hexes=10, seed=7).load_observations()
    b = SyntheticSource(year_start=2016, year_end=2020, n_hexes=10, seed=7).load_observations()
    pd.testing.assert_frame_equal(a, b)


def test_earthengine_source_missing_file_raises_clear_error(tmp_path):
    missing = tmp_path / "observations.parquet"
    source = EarthEngineSource(observations_file=missing)
    with pytest.raises(FileNotFoundError):
        source.load_observations()


def test_earthengine_source_reads_matching_schema(tmp_path):
    path = tmp_path / "observations.parquet"
    df = pd.DataFrame({
        "h3_index": ["89abc"] * 2,
        "year": [2016, 2017],
        "built_frac_soft": [0.1, 0.12],
        "built_frac_hard": [0.09, 0.11],
        "n_pixels": [1000, 1000],
        "n_scenes": [20, 18],
    })
    df.to_parquet(path, index=False)

    source = EarthEngineSource(observations_file=path)
    loaded = source.load_observations()
    assert set(OBSERVATION_COLUMNS) <= set(loaded.columns)
    assert source.provenance.startswith("LIVE")
