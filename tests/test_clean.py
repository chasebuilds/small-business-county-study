import math

import numpy as np
import pandas as pd
import pytest

from sbcs import clean


def test_naics_clean_and_level():
    assert clean.naics_clean("------") == "ALL"
    assert clean.naics_clean("23----") == "23"
    assert clean.naics_clean("236///") == "236"
    assert clean.naics_clean("7225//") == "7225"
    assert clean.naics_level("ALL") == 0
    assert clean.naics_level("7225") == 4


def test_fips5_pads_state_and_county():
    assert clean.fips5("21", "1") == "21001"
    assert clean.fips5(21, 195) == "21195"


@pytest.mark.parametrize(
    ("flag", "empflag", "expected"),
    [
        ("G", "", False),
        ("H", None, False),
        ("J", np.nan, False),
        ("D", "", True),
        ("S", "", True),
        ("N", "", True),
        ("G", "r", False),  # lowercase r = revised figure, number is real
        ("G", "C", True),  # uppercase letter = size range, value withheld
        (np.nan, np.nan, False),
    ],
)
def test_emp_is_suppressed(flag, empflag, expected):
    assert clean.emp_is_suppressed(flag, empflag) is expected


def _raw_county():
    return pd.DataFrame(
        {
            "fipstate": ["21", "21", "21"],
            "fipscty": ["195", "195", "071"],
            "naics": ["------", "23----", "23----"],
            "emp_nf": ["G", "D", "J"],
            "emp": ["1000", "0", "55"],
            "est": ["90", "7", "3"],
            "n<5": ["40", "4", "2"],
            "n5_9": ["20", "2", "1"],
        }
    )


def test_clean_cbp_county_withholds_instead_of_zero():
    out = clean.clean_cbp(_raw_county(), 2022, "county")
    assert list(out["fips"]) == ["21195", "21195", "21071"]
    assert list(out["naics"]) == ["ALL", "23", "23"]
    assert out.loc[1, "emp_flag"] == "SUP"
    assert math.isnan(out.loc[1, "emp"])  # withheld is NaN, never 0
    assert out.loc[2, "emp"] == 55
    assert out.loc[2, "emp_flag"] == "J"
    assert out.loc[0, "n_lt5"] == 40
    assert math.isnan(out.loc[0, "n20_49"])  # column absent in input


def test_clean_cbp_national_keeps_all_forms_row_only():
    raw = pd.DataFrame(
        {
            "uscode": ["98", "98"],
            "naics": ["------", "------"],
            "lfo": ["-", "C"],
            "emp_nf": ["G", "G"],
            "emp": ["100", "60"],
            "est": ["10", "6"],
            "n1_4": ["5", "3"],
        }
    )
    out = clean.clean_cbp(raw, 2012, "national")
    assert len(out) == 1
    assert out.loc[0, "fips"] == "00000"
    assert out.loc[0, "n_lt5"] == 5  # old n1_4 column renamed


def test_region_total_propagates_missing():
    assert clean.region_total(pd.DataFrame({"emp": [1.0, 2.0]}), "emp") == 3.0
    assert math.isnan(clean.region_total(pd.DataFrame({"emp": [1.0, np.nan]}), "emp"))


def test_region_by_naics_sums_est_but_not_partial_emp():
    df = pd.DataFrame(
        {
            "year": [2022, 2022, 2022, 2022],
            "fips": ["a", "b", "a", "b"],
            "naics": ["23", "23", "44", "44"],
            "est": [3, 4, 5, 6],
            "emp": [10.0, np.nan, 7.0, 8.0],
            **{c: [1.0] * 4 for c in clean.SIZE_COLUMNS},
        }
    )
    out = clean.region_by_naics(df).set_index("naics")
    assert out.loc["23", "est"] == 7
    assert math.isnan(out.loc["23", "emp"])
    assert out.loc["23", "emp_missing"] == 1
    assert out.loc["44", "emp"] == 15
    assert out.loc["44", "counties"] == 2


def test_per_1000():
    assert clean.per_1000(50, 10_000) == 5.0
    s = clean.per_1000(pd.Series([10, 20]), pd.Series([1000, 2000]))
    assert list(s) == [10.0, 10.0]


def test_index_to_base():
    out = clean.index_to_base(pd.Series([50.0, 75.0, 100.0]))
    assert list(out) == [100.0, 150.0, 200.0]
    assert clean.index_to_base(pd.Series([np.nan, 1.0])).isna().all()
    assert clean.index_to_base(pd.Series([0.0, 1.0])).isna().all()


def test_small_share():
    row = pd.Series({"est": 100, "n_lt5": 50, "n5_9": 20, "n10_19": 10})
    assert clean.small_share(row) == pytest.approx(0.8)
    row["n5_9"] = np.nan
    assert math.isnan(clean.small_share(row))


def test_parse_acs_table_and_geo_helpers():
    lines = [
        "GEO_ID|B19013_E001|B19013_M001\n",
        "0100000US|80734|166\n",
        "0400000US21|63726|429\n",
        "0500000US21195|44312|3223\n",
        "0500000US21071|-666666666|**\n",
    ]
    df = clean.parse_acs_table(lines)
    assert df["B19013_E001"].iloc[0] == 80734
    assert df["B19013_M001"].isna().iloc[3]  # '**' becomes missing
    assert [clean.geo_kind(g) for g in df["GEO_ID"]] == ["national", "state", "county", "county"]
    assert [clean.geo_fips(g) for g in df["GEO_ID"]] == ["00000", "21000", "21195", "21071"]
    assert clean.geo_kind("1400000US21195000100") == ""


def test_share_and_income_unreliable():
    assert clean.share(1, 4) == 25.0
    assert math.isnan(clean.share(1, 0))
    assert math.isnan(clean.share(1, np.nan))
    assert clean.income_unreliable(50000, 6000) is True
    assert clean.income_unreliable(50000, 4000) is False
    assert clean.income_unreliable(np.nan, 100) is True
