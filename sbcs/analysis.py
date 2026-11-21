"""Turn the committed extracts into the tables behind every chart and sentence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import clean
from .sources import ACS_VINTAGE, LATEST_CBP

ROOT = Path(__file__).resolve().parents[1]
EXTRACTS = ROOT / "data" / "extracts"
GEOS = ("Eastern KY", "Kentucky", "United States")
SECTOR_BASE_YEAR = 2018  # first year every county-sector employment value is published
ACS_LABEL = f"ACS {ACS_VINTAGE - 4}-{ACS_VINTAGE} 5-year"


@dataclass
class Data:
    cbp: pd.DataFrame
    acs: pd.DataFrame
    pop: pd.DataFrame
    counties: pd.DataFrame
    titles: dict[str, str]


def load(extracts: Path = EXTRACTS) -> Data:
    cbp = pd.read_csv(extracts / "cbp.csv", dtype={"fips": str, "naics": str})
    acs = pd.read_csv(extracts / "acs.csv", dtype={"fips": str})
    pop = pd.read_csv(extracts / "pop.csv", dtype={"fips": str})
    counties = pd.read_csv(extracts / "counties.csv", dtype={"fips": str})
    titles = pd.read_csv(extracts / "naics_titles.csv", dtype=str)
    return Data(cbp, acs, pop, counties, dict(zip(titles["naics"], titles["title"], strict=True)))


def _pop(data: Data) -> dict[str, float]:
    latest = f"pop_{LATEST_CBP}"
    return dict(zip(data.pop["fips"], data.pop[latest], strict=True))


def geo_rows(data: Data, year: int, naics: str) -> dict[str, pd.Series]:
    """Establishment, employment and size rows for region, KY and US for one year and code."""
    c = data.cbp
    sel = c[(c["year"] == year) & (c["naics"] == naics)]
    counties = sel[sel["geo"] == "county"]
    region = clean.region_by_naics(counties).iloc[0]
    state = sel[sel["geo"] == "state"].iloc[0]
    nation = sel[sel["geo"] == "national"].iloc[0]
    return {"Eastern KY": region, "Kentucky": state, "United States": nation}


def population(data: Data) -> dict[str, float]:
    pops = _pop(data)
    region = sum(pops[f] for f in data.counties["fips"])
    return {"Eastern KY": region, "Kentucky": pops["21000"], "United States": pops["00000"]}


def sector_codes(data: Data) -> list[str]:
    return sorted({n for n in data.cbp["naics"].unique() if len(n) == 2 and n != "99"})


def label(data: Data, code: str) -> str:
    return "All sectors" if code == "ALL" else data.titles.get(code, code)


def estab_per_1000_by_sector(data: Data) -> pd.DataFrame:
    """Establishments per 1,000 residents, latest CBP year, by 2-digit sector."""
    pops = population(data)
    rows = []
    for code in ["ALL", *sector_codes(data)]:
        geos = geo_rows(data, LATEST_CBP, code)
        row = {"naics": code, "sector": label(data, code)}
        for g in GEOS:
            row[g] = float(clean.per_1000(geos[g]["est"], pops[g]))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["ratio_vs_ky"] = out["Eastern KY"] / out["Kentucky"]
    return out


def county_total_estab(data: Data) -> pd.DataFrame:
    """Total establishments per 1,000 residents for each county."""
    pops = _pop(data)
    c = data.cbp
    sel = c[(c["year"] == LATEST_CBP) & (c["naics"] == "ALL") & (c["geo"] == "county")]
    out = data.counties.merge(sel[["fips", "est", "emp", "n_lt5", "n5_9", "n10_19"]], on="fips")
    out["pop"] = out["fips"].map(pops)
    out["est_per_1000"] = clean.per_1000(out["est"], out["pop"])
    out["emp_per_1000"] = clean.per_1000(out["emp"], out["pop"])
    out["small_share"] = out[["n_lt5", "n5_9", "n10_19"]].sum(axis=1) / out["est"] * 100
    return out.sort_values("est_per_1000").reset_index(drop=True)


def totals_trend(data: Data) -> pd.DataFrame:
    """Employment and establishments by year for the three geographies, indexed to 2012."""
    rows = []
    for year in sorted(data.cbp["year"].unique()):
        geos = geo_rows(data, year, "ALL")
        for g in GEOS:
            rows.append({"year": year, "geo": g, "emp": geos[g]["emp"], "est": geos[g]["est"]})
    df = pd.DataFrame(rows)
    for col in ("emp", "est"):
        df[f"{col}_idx"] = df.groupby("geo")[col].transform(clean.index_to_base)
    return df


def sector_emp_change(data: Data) -> pd.DataFrame:
    """Percent change in employment from SECTOR_BASE_YEAR to the latest year, by sector.

    Only reported when every county has a published value in both years.
    """
    rows = []
    for code in sector_codes(data):
        a = geo_rows(data, SECTOR_BASE_YEAR, code)
        b = geo_rows(data, LATEST_CBP, code)
        row = {"naics": code, "sector": label(data, code)}
        for g in GEOS:
            start, end = a[g]["emp"], b[g]["emp"]
            ok = pd.notna(start) and pd.notna(end) and start
            row[g] = (end / start - 1) * 100 if ok else float("nan")
        row["emp_latest"] = b["Eastern KY"]["emp"]
        row["est_latest"] = b["Eastern KY"]["est"]
        rows.append(row)
    return pd.DataFrame(rows)


def business_types(data: Data, top: int = 12) -> pd.DataFrame:
    """Most common 4-digit industry groups in the region, by establishments.

    ``lq`` is the establishment share in the region divided by the US share (1.0 = same).
    """
    c = data.cbp
    latest = c[c["year"] == LATEST_CBP]
    four = latest[latest["naics"].str.len() == 4]
    four = four[~four["naics"].str.startswith("99")]
    region = four[four["geo"] == "county"].groupby("naics")["est"].sum()
    nation = four[four["geo"] == "national"].set_index("naics")["est"]
    total_r = geo_rows(data, LATEST_CBP, "ALL")["Eastern KY"]["est"]
    total_n = geo_rows(data, LATEST_CBP, "ALL")["United States"]["est"]
    out = pd.DataFrame({"est": region})
    out["share_pct"] = out["est"] / total_r * 100
    out["us_share_pct"] = nation.reindex(out.index) / total_n * 100
    out["lq"] = out["share_pct"] / out["us_share_pct"]
    out["industry"] = [label(data, n) for n in out.index]
    out = out.sort_values("est", ascending=False).head(top)
    return out.rename_axis("naics").reset_index()


def size_mix(data: Data) -> pd.DataFrame:
    """Share of establishments by size class for the three geographies, latest year.

    Only the classes published for every county are used: under 5, 5 to 9, 10 to 19
    employees, and 20 or more (the remainder).
    """
    geos = geo_rows(data, LATEST_CBP, "ALL")
    rows = []
    for g in GEOS:
        r = geos[g]
        small = clean.SMALL_SIZE_COLUMNS
        row = {"geo": g, "est": r["est"], "emp": r["emp"]}
        for col in small:
            row[col] = r[col] / r["est"] * 100
        row["n20_plus"] = (r["est"] - sum(r[c] for c in small)) / r["est"] * 100
        row["small_share"] = clean.small_share(r) * 100
        row["emp_per_est"] = r["emp"] / r["est"]
        rows.append(row)
    return pd.DataFrame(rows)


def acs_county(data: Data) -> pd.DataFrame:
    """County table of broadband, no-internet and income with reliability flags."""
    cty = data.acs[data.acs["geo"] == "county"]
    cty = data.counties.merge(cty, on="fips").copy()
    tot = cty["hh_total"]
    for src, dst in (
        ("hh_broadband", "broadband_pct"),
        ("hh_internet", "internet_pct"),
        ("hh_no_internet", "no_internet_pct"),
        ("hh_cellular_only", "cellular_only_pct"),
    ):
        cty[dst] = [clean.share(n, d) for n, d in zip(cty[src], tot, strict=True)]
    cty["income_unreliable"] = [
        clean.income_unreliable(e, m) for e, m in zip(cty["income"], cty["income_moe"], strict=True)
    ]
    return cty.sort_values("broadband_pct").reset_index(drop=True)


def acs_summary(data: Data) -> pd.DataFrame:
    """Region, Kentucky and US broadband / internet shares and income."""
    a = data.acs
    cty = acs_county(data)
    reg_total = cty["hh_total"].sum()
    rows = [
        {
            "geo": "Eastern KY",
            "broadband_pct": clean.share(cty["hh_broadband"].sum(), reg_total),
            "no_internet_pct": clean.share(cty["hh_no_internet"].sum(), reg_total),
            "cellular_only_pct": clean.share(cty["hh_cellular_only"].sum(), reg_total),
            "income": float(cty["income"].median()),
            "income_note": "median of the 31 county medians, not a true regional median",
        }
    ]
    for key, name in (("state", "Kentucky"), ("national", "United States")):
        r = a[a["geo"] == key].iloc[0]
        rows.append(
            {
                "geo": name,
                "broadband_pct": clean.share(r["hh_broadband"], r["hh_total"]),
                "no_internet_pct": clean.share(r["hh_no_internet"], r["hh_total"]),
                "cellular_only_pct": clean.share(r["hh_cellular_only"], r["hh_total"]),
                "income": float(r["income"]),
                "income_note": "published ACS median",
            }
        )
    return pd.DataFrame(rows)


def suppression_report(data: Data) -> pd.DataFrame:
    """Per year: share of county x sector employment cells withheld or noisy."""
    c = data.cbp
    sec = c[(c["geo"] == "county") & (c["naics"].str.len() == 2)]
    rows = []
    for year, grp in sec.groupby("year"):
        rows.append(
            {
                "year": year,
                "cells": len(grp),
                "withheld_pct": grp["emp"].isna().mean() * 100,
                "noise_5pct_plus_pct": (grp["emp_flag"] == "J").mean() * 100,
            }
        )
    return pd.DataFrame(rows)
