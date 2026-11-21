"""Every raw source: URL, vintage and what it is used for."""

from __future__ import annotations

CBP_YEARS = list(range(2012, 2024))
LATEST_CBP = max(CBP_YEARS)
ACS_VINTAGE = 2024
POP_FILE = "co-est2024-alldata.csv"

CBP_BASE = "https://www2.census.gov/programs-surveys/cbp/datasets"
ACS_BASE = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/"
    f"{ACS_VINTAGE}/table-based-SF/data/5YRData"
)
POP_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/"
    + POP_FILE
)
NAICS_URL = (
    "https://www2.census.gov/programs-surveys/cbp/technical-documentation/"
    "reference/naics-descriptions/naics2017.txt"
)

ACS_TABLES = {
    "b01003": "Total population",
    "b19013": "Median household income (inflation-adjusted dollars)",
    "b28002": "Presence and types of internet subscriptions in household",
}


def sources() -> list[dict]:
    """Return every raw file the study downloads, in a stable order."""
    out: list[dict] = []
    for year in CBP_YEARS:
        yy = str(year)[2:]
        for geo, label in (("co", "county"), ("st", "state"), ("us", "national")):
            out.append(
                {
                    "file": f"cbp{yy}{geo}.zip",
                    "url": f"{CBP_BASE}/{year}/cbp{yy}{geo}.zip",
                    "what": f"County Business Patterns {year}, {label} file",
                    "vintage": str(year),
                }
            )
    for table, title in ACS_TABLES.items():
        out.append(
            {
                "file": f"acsdt5y{ACS_VINTAGE}-{table}.dat",
                "url": f"{ACS_BASE}/acsdt5y{ACS_VINTAGE}-{table}.dat",
                "what": f"ACS {ACS_VINTAGE - 4}-{ACS_VINTAGE} 5-year, {table.upper()}: {title}",
                "vintage": f"{ACS_VINTAGE - 4}-{ACS_VINTAGE}",
            }
        )
    out.append(
        {
            "file": POP_FILE,
            "url": POP_URL,
            "what": "Population estimates, Vintage 2024, county totals",
            "vintage": "2024",
        }
    )
    out.append(
        {
            "file": "naics2017.txt",
            "url": NAICS_URL,
            "what": "CBP NAICS code descriptions",
            "vintage": "NAICS 2017",
        }
    )
    return out
