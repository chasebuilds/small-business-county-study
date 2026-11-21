import hashlib
import json
from pathlib import Path

import pytest

from sbcs import analysis, report

EXTRACTS = Path(__file__).resolve().parents[1] / "data" / "extracts"


@pytest.fixture(scope="module")
def data():
    return analysis.load()


def test_extract_files_match_manifest():
    manifest = json.loads((EXTRACTS / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest
    for name, digest in manifest.items():
        assert hashlib.sha256((EXTRACTS / name).read_bytes()).hexdigest() == digest, name


def test_region_has_31_counties_and_population(data):
    assert len(data.counties) == 31
    assert data.counties["fips"].str.startswith("21").all()
    pops = analysis.population(data)
    assert 400_000 < pops["Eastern KY"] < 1_000_000
    assert pops["Eastern KY"] < pops["Kentucky"] < pops["United States"]


def test_total_rate_matches_hand_calculation(data):
    tot = analysis.estab_per_1000_by_sector(data).set_index("naics").loc["ALL"]
    rows = analysis.geo_rows(data, analysis.LATEST_CBP, "ALL")
    pop = analysis.population(data)["Eastern KY"]
    assert tot["Eastern KY"] == pytest.approx(rows["Eastern KY"]["est"] / pop * 1000)


def test_county_estab_covers_every_county(data):
    df = analysis.county_total_estab(data)
    assert len(df) == 31
    assert df["est_per_1000"].notna().all()


def test_trend_indexes_start_at_100_and_region_total_is_complete(data):
    trend = analysis.totals_trend(data)
    first = trend[trend["year"] == trend["year"].min()]
    assert (first["emp_idx"].round(6) == 100).all()
    assert trend[trend["geo"] == "Eastern KY"]["emp"].notna().all()


def test_sector_change_only_where_all_counties_publish(data):
    df = analysis.sector_emp_change(data)
    assert df["Eastern KY"].notna().sum() >= 15


def test_suppression_report_shows_old_years_withheld(data):
    rep = analysis.suppression_report(data).set_index("year")
    assert rep.loc[2012, "withheld_pct"] > 20
    assert rep.loc[analysis.LATEST_CBP, "withheld_pct"] == 0


def test_business_types_sorted_and_share_sums_below_100(data):
    df = analysis.business_types(data)
    assert df["est"].is_monotonic_decreasing
    assert df["share_pct"].sum() < 100


def test_acs_summary_has_three_geographies(data):
    s = analysis.acs_summary(data)
    assert list(s["geo"]) == list(analysis.GEOS)
    assert s["broadband_pct"].between(50, 100).all()


def test_report_builds_offline(data, tmp_path):
    out = report.build(data, tmp_path / "index.html")
    text = out.read_text(encoding="utf-8")
    assert "Findings in plain English" in text
    assert "withheld" in text
    assert chr(0x2014) not in text
    found = json.loads((tmp_path / "findings.json").read_text(encoding="utf-8"))
    assert 50 < found["broadband_pct"]["Eastern KY"] < 100
