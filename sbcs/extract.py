"""Cut the big raw files down to small Kentucky/US extracts that are safe to commit.

Raw files are large and live in data/raw (git-ignored). The extracts hold only the 31
Eastern Kentucky counties, Kentucky and the US, so tests and CI run with no network.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd

from . import clean
from .sources import ACS_VINTAGE, CBP_YEARS, LATEST_CBP, POP_FILE

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXTRACTS = ROOT / "data" / "extracts"
COUNTIES = ROOT / "data" / "counties.csv"
KY = "21"
LF = chr(10)


def load_population(path: Path) -> pd.DataFrame:
    """County, Kentucky and US population (2023 and 2024 estimates) from the popest file.

    The file has no national row. The US total is the sum of the 50 states and DC, which
    matches CBP's coverage (CBP excludes Puerto Rico).
    """
    raw = pd.read_csv(path, encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
    states = raw[raw["SUMLEV"] == 40]
    ky = raw[(raw["STATE"] == KY) & raw["SUMLEV"].isin([40, 50])]
    geo = ky["SUMLEV"].map({40: "state", 50: "county"})
    out = pd.DataFrame(
        {
            "fips": [f"{st}{co}" for st, co in zip(ky["STATE"], ky["COUNTY"], strict=True)],
            "geo": geo.to_numpy(),
            "name": ky["CTYNAME"].str.replace(" County", "", regex=False).to_numpy(),
            "pop_2023": ky["POPESTIMATE2023"].to_numpy(),
            "pop_2024": ky["POPESTIMATE2024"].to_numpy(),
        }
    )
    nation = pd.DataFrame(
        [
            {
                "fips": "00000",
                "geo": "national",
                "name": "United States",
                "pop_2023": states["POPESTIMATE2023"].sum(),
                "pop_2024": states["POPESTIMATE2024"].sum(),
            }
        ]
    )
    return pd.concat([out, nation], ignore_index=True)


def eky_fips(pop: pd.DataFrame) -> pd.DataFrame:
    """Join the county list to FIPS codes; fail loudly if a name does not match."""
    counties = pd.read_csv(COUNTIES)
    ky = pop[pop["geo"] == "county"].copy()
    ky = ky[ky["fips"].str.startswith(KY)]
    merged = counties.merge(ky[["fips", "name"]], left_on="county", right_on="name", how="left")
    if merged["fips"].isna().any():
        missing = merged.loc[merged["fips"].isna(), "county"].tolist()
        raise SystemExit(f"county names not found in population file: {missing}")
    return merged[["fips", "county", "district"]]


def extract_cbp(keep_fips: set[str]) -> pd.DataFrame:
    frames = []
    for year in CBP_YEARS:
        yy = str(year)[2:]
        for geo in ("county", "state", "national"):
            suffix = {"county": "co", "state": "st", "national": "us"}[geo]
            with zipfile.ZipFile(RAW / f"cbp{yy}{suffix}.zip") as zf:
                member = zf.namelist()[0]
                with zf.open(member) as handle:
                    raw = pd.read_csv(handle, dtype=str, encoding="latin-1")
            raw.columns = [c.strip().lower() for c in raw.columns]
            if geo != "national":
                raw = raw[raw["fipstate"] == KY]
            cleaned = clean.clean_cbp(raw, year, geo)
            if geo == "county":
                cleaned = cleaned[cleaned["fips"].isin(keep_fips)]
            elif geo == "state":
                cleaned = cleaned[cleaned["fips"] == "21000"]
            level = cleaned["naics"].map(clean.naics_level)
            cleaned = cleaned[(level <= 2) | ((level <= 4) & (year == LATEST_CBP))]
            frames.append(cleaned)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["year", "geo", "fips", "naics"]).reset_index(drop=True)


def extract_acs(keep_fips: set[str]) -> pd.DataFrame:
    wanted = {
        "b01003": {"B01003_E001": "pop"},
        "b19013": {"B19013_E001": "income", "B19013_M001": "income_moe"},
        "b28002": {
            "B28002_E001": "hh_total",
            "B28002_E002": "hh_internet",
            "B28002_E004": "hh_broadband",
            "B28002_E006": "hh_cellular_only",
            "B28002_E013": "hh_no_internet",
        },
    }
    merged: pd.DataFrame | None = None
    for table, cols in wanted.items():
        path = RAW / f"acsdt5y{ACS_VINTAGE}-{table}.dat"
        with path.open(encoding="utf-8", errors="replace") as handle:
            header = handle.readline()
            lines = [header]
            for line in handle:
                gid = line.split("|", 1)[0]
                kind = clean.geo_kind(gid)
                keep = (
                    kind == "national"
                    or (kind == "state" and gid.endswith(KY))
                    or (kind == "county" and gid[-5:] in keep_fips)
                )
                if keep:
                    lines.append(line)
        df = clean.parse_acs_table(lines)
        df["fips"] = df["GEO_ID"].map(clean.geo_fips)
        df["geo"] = df["GEO_ID"].map(clean.geo_kind)
        df = df[["fips", "geo", *cols.keys()]].rename(columns=cols)
        merged = df if merged is None else merged.merge(df, on=["fips", "geo"], how="outer")
    assert merged is not None
    return merged.sort_values("fips").reset_index(drop=True)


def extract_naics_titles() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "naics2017.txt", dtype=str, encoding="latin-1")
    raw.columns = [c.strip().upper() for c in raw.columns]
    raw["naics"] = raw["NAICS"].map(clean.naics_clean)
    raw["title"] = raw["DESCRIPTION"].str.strip()
    out = raw[raw["naics"].map(clean.naics_level) <= 4][["naics", "title"]]
    return out.drop_duplicates("naics").reset_index(drop=True)


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> None:
    EXTRACTS.mkdir(parents=True, exist_ok=True)
    pop = load_population(RAW / POP_FILE)
    counties = eky_fips(pop)
    keep = set(counties["fips"])
    pop = pop[pop["fips"].isin(keep | {"21000", "00000"})]
    counties.to_csv(EXTRACTS / "counties.csv", index=False, lineterminator=LF)
    pop.to_csv(EXTRACTS / "pop.csv", index=False, lineterminator=LF)
    extract_cbp(keep).to_csv(EXTRACTS / "cbp.csv", index=False, lineterminator=LF)
    extract_acs(keep).to_csv(EXTRACTS / "acs.csv", index=False, lineterminator=LF)
    extract_naics_titles().to_csv(EXTRACTS / "naics_titles.csv", index=False, lineterminator=LF)
    manifest = {p.name: sha256_text(p) for p in sorted(EXTRACTS.glob("*.csv"))}
    (EXTRACTS / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for name in manifest:
        print(name, (EXTRACTS / name).stat().st_size, "bytes")


if __name__ == "__main__":
    run()
