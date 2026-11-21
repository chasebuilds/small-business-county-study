"""Build docs/index.html. Every number in the findings is computed from the extracts."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from . import analysis

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
:root{--ink:#2a2019;--ink2:rgba(42,32,25,.68);--glass:rgba(255,250,244,.34);--edge:rgba(255,255,255,.6);
--card:rgba(255,252,248,.66);--accent:#0f766e;--warn:#a8670f;--shadow:rgba(70,40,20,.22)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--ink:#f6ece2;--ink2:rgba(246,236,226,.72);
--glass:rgba(34,24,18,.42);--edge:rgba(255,255,255,.16);--card:rgba(48,36,28,.62);--accent:#4fd1c4;--warn:#f0b45a;--shadow:rgba(0,0,0,.5)}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;color:var(--ink);font:16px/1.6 "Segoe UI",system-ui,sans-serif;min-height:100vh;
background:radial-gradient(60% 50% at 80% 10%,#fff6e6,transparent 70%),linear-gradient(180deg,#e9ddcf,#cdb9a3 60%,#b89a80);background-attachment:fixed}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) body{background:radial-gradient(60% 50% at 80% 10%,#4a3320,transparent 70%),linear-gradient(180deg,#3b2c22,#2a1f19 60%,#241a14);background-attachment:fixed}}
.nav{position:sticky;top:12px;z-index:5;display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin:12px auto 0;width:fit-content;max-width:calc(100% - 24px);
padding:6px;border-radius:999px;background:var(--glass);backdrop-filter:blur(22px) saturate(150%);-webkit-backdrop-filter:blur(22px) saturate(150%);border:1px solid var(--edge);box-shadow:0 14px 40px -16px var(--shadow)}
.nav a{color:var(--ink);text-decoration:none;font-size:13px;padding:6px 12px;border-radius:999px}.nav a:hover,.nav a:focus-visible{background:var(--card);outline:none}
main{max-width:980px;margin:0 auto;padding:18px 16px 60px;display:flex;flex-direction:column;gap:18px}
.glass{background:var(--glass);backdrop-filter:blur(26px) saturate(150%);-webkit-backdrop-filter:blur(26px) saturate(150%);
border:1px solid var(--edge);border-radius:26px;padding:clamp(18px,3vw,30px);box-shadow:inset 0 1px 0 var(--edge),0 24px 60px -24px var(--shadow)}
h1{font-size:clamp(26px,4vw,38px);line-height:1.15;margin:0 0 8px;letter-spacing:-.02em}
h2{font-size:22px;margin:0 0 10px;letter-spacing:-.01em}h3{font-size:16px;margin:18px 0 6px}
p{margin:0 0 12px;max-width:72ch}.lead{color:var(--ink2);font-size:17px}
ul{margin:0 0 12px;padding-left:20px;max-width:72ch}li{margin-bottom:6px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:18px 0 0}
.tile{background:var(--card);border:1px solid var(--edge);border-radius:18px;padding:14px 16px}
.tile b{display:block;font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}.tile span{font-size:13px;color:var(--ink2)}
figure{margin:14px 0 4px;background:#fff;border-radius:16px;padding:8px;border:1px solid var(--edge)}
figure img{width:100%;height:auto;display:block;border-radius:10px}
figcaption{font-size:13px;color:#4a3d33;padding:6px 8px 2px}
.caveat{background:rgba(200,130,20,.14);border-left:4px solid var(--warn);padding:10px 14px;border-radius:10px;margin:12px 0;max-width:72ch}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:8px 10px;border-top:1px solid var(--edge)}
th{font-weight:600;font-size:13px;color:var(--ink2);border-top:0}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}a{color:var(--accent)}code{font-family:ui-monospace,Consolas,monospace;font-size:13px}
footer{font-size:13px;color:var(--ink2);text-align:center;padding:10px}
"""


def _f(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def _table(df: pd.DataFrame, cols: list[tuple[str, str, int | None]]) -> str:
    head = "".join(
        "<th{}>{}</th>".format(' class="n"' if nd is not None else "", html.escape(t))
        for _, t, nd in cols
    )
    body = []
    for _, r in df.iterrows():
        cells = []
        for key, _, nd in cols:
            v = r[key]
            if nd is None:
                cells.append(f"<td>{html.escape(str(v))}</td>")
            else:
                cells.append(f'<td class="n">{_f(v, nd) if pd.notna(v) else "withheld"}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def name_ratio_row(r: pd.Series) -> str:
    return f"{r['sector']} ({r['Eastern KY']:.2f} vs {r['Kentucky']:.2f} for Kentucky)"


def findings(data: analysis.Data) -> dict:
    """All numbers used in the prose, computed once."""
    pops = analysis.population(data)
    by_sector = analysis.estab_per_1000_by_sector(data).set_index("naics")
    trend = analysis.totals_trend(data)
    last = trend["year"].max()
    first = trend["year"].min()

    def idx(g: str, col: str, yr: int) -> float:
        return float(trend[(trend["geo"] == g) & (trend["year"] == yr)][col].iloc[0])

    acs = analysis.acs_summary(data).set_index("geo")
    cty = analysis.acs_county(data)
    sizes = analysis.size_mix(data).set_index("geo")
    sect = analysis.sector_emp_change(data)
    sect = sect[sect["emp_latest"] >= 1000].sort_values("Eastern KY")
    types = analysis.business_types(data)
    over = by_sector.drop(index="ALL").sort_values("ratio_vs_ky", ascending=False)
    corr = float(cty["income"].corr(cty["broadband_pct"]))
    return {
        "pops": pops,
        "last": int(last),
        "first": int(first),
        "tot": by_sector.loc["ALL"],
        "emp_idx": {g: idx(g, "emp_idx", last) for g in analysis.GEOS},
        "est_idx": {g: idx(g, "est_idx", last) for g in analysis.GEOS},
        "emp_region_first": idx("Eastern KY", "emp", first),
        "emp_region_last": idx("Eastern KY", "emp", last),
        "acs": acs,
        "cty": cty,
        "sizes": sizes,
        "sect": sect,
        "types": types,
        "over": over,
        "corr": corr,
        "unreliable": int(cty["income_unreliable"].sum()),
        "supp": analysis.suppression_report(data),
    }


def build(data: analysis.Data | None = None, out: Path | None = None) -> Path:
    data = data or analysis.load()
    out = out or DOCS / "index.html"
    s = findings(data)
    tot, acs, sizes = s["tot"], s["acs"], s["sizes"]
    cty = s["cty"]
    last = s["last"]
    pops = s["pops"]
    types = s["types"]
    sect = s["sect"]
    supp = s["supp"].set_index("year")
    growth = sect.sort_values("Eastern KY", ascending=False)
    ratio = tot["Eastern KY"] / tot["Kentucky"]
    more = s["over"][s["over"]["ratio_vs_ky"] > 1.05]
    fewest = s["over"].tail(3).iloc[::-1]
    more_text = " and ".join(name_ratio_row(r) for _, r in more.iterrows())
    fewest_text = ", ".join(name_ratio_row(r) for _, r in fewest.iterrows())
    gap_sentence = (
        f"Relative to Kentucky, the region has more establishments per resident in {more_text}. "
        if len(more)
        else "No sector has clearly more establishments per resident than Kentucky. "
    ) + f"It has the fewest, relative to Kentucky, in {fewest_text}."
    worst = cty.iloc[0]
    best = cty.iloc[-1]

    tiles = f"""
<div class="tiles">
<div class="tile"><b>{_f(tot['Eastern KY'])}</b><span>establishments per 1,000 residents in the 31 counties, {last}. Kentucky {_f(tot['Kentucky'])}, US {_f(tot['United States'])}.</span></div>
<div class="tile"><b>{_f(s['emp_idx']['Eastern KY'] - 100)}%</b><span>change in payroll jobs, {s['first']} to {last}. Kentucky {_f(s['emp_idx']['Kentucky'] - 100)}%, US {_f(s['emp_idx']['United States'] - 100)}%.</span></div>
<div class="tile"><b>{_f(acs.loc['Eastern KY', 'broadband_pct'])}%</b><span>of households with broadband. Kentucky {_f(acs.loc['Kentucky', 'broadband_pct'])}%, US {_f(acs.loc['United States', 'broadband_pct'])}%.</span></div>
<div class="tile"><b>${_f(acs.loc['Eastern KY', 'income'], 0)}</b><span>typical county median household income (median of 31 county medians). Kentucky ${_f(acs.loc['Kentucky', 'income'], 0)}, US ${_f(acs.loc['United States', 'income'], 0)}.</span></div>
</div>"""

    def fig(name: str, caption: str) -> str:
        return f'<figure><img src="charts/{name}" alt="{html.escape(caption)}" loading="lazy"><figcaption>{html.escape(caption)}</figcaption></figure>'

    type_table = _table(
        types,
        [
            ("industry", "Industry group (4-digit NAICS)", None),
            ("est", "Establishments", 0),
            ("share_pct", "% of Eastern KY", 1),
            ("us_share_pct", "% of US", 1),
            ("lq", "Ratio to US share", 2),
        ],
    )
    cty_table = _table(
        cty.sort_values("county"),
        [
            ("county", "County", None),
            ("district", "District", None),
            ("broadband_pct", "Broadband %", 1),
            ("no_internet_pct", "No internet %", 1),
            ("income", "Median income $", 0),
            ("income_moe", "Income margin of error $", 0),
        ],
    )
    supp_rows = supp.loc[[2012, 2015, 2017, 2018, last]]
    supp_table = _table(
        supp_rows.reset_index(),
        [
            ("year", "Year", 0),
            ("withheld_pct", "% county-sector employment cells withheld", 1),
            ("noise_5pct_plus_pct", "% flagged noise of 5% or more", 1),
        ],
    )
    for y in (2012, 2015, 2017, 2018, last):
        supp_table = supp_table.replace(f">{y:,}<", f">{y}<")

    sect_up = ", ".join(f"{r['sector']} ({r['Eastern KY']:+.0f}%)" for _, r in growth.head(3).iterrows())
    sect_dn = ", ".join(f"{r['sector']} ({r['Eastern KY']:+.0f}%)" for _, r in growth.tail(3).iloc[::-1].iterrows())

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Small Business in Eastern Kentucky Counties</title>
<meta name="description" content="Reproducible analysis of small-business conditions in 31 Eastern Kentucky counties versus Kentucky and the US, from free Census data.">
<style>{CSS}</style></head><body>
<nav class="nav" aria-label="Sections"><a href="#findings">Findings</a><a href="#density">Density</a><a href="#jobs">Jobs</a><a href="#types">Business types</a><a href="#internet">Broadband</a><a href="#income">Income</a><a href="#caveats">Caveats</a><a href="#sources">Sources</a></nav>
<main>
<section class="glass"><h1>Small business in Eastern Kentucky counties</h1>
<p class="lead">31 counties in five eastern Kentucky development districts, compared with Kentucky and the United States, using free public Census Bureau data.</p>
{tiles}
<p style="margin-top:14px">Business figures are for {last} (County Business Patterns). Internet and income figures are the {analysis.ACS_LABEL} estimates. Population is the Census {last} estimate ({_f(pops['Eastern KY'], 0)} residents in the region). Code and data: <a href="https://github.com/chasebuilds/small-business-county-study">github.com/chasebuilds/small-business-county-study</a>.</p></section>

<section class="glass" id="findings"><h2>Findings in plain English</h2>
<ul>
<li><b>Fewer businesses per person.</b> The region has {_f(tot['Eastern KY'])} establishments per 1,000 residents. That is {_f(ratio * 100, 0)}% of Kentucky's rate and {_f(tot['Eastern KY'] / tot['United States'] * 100, 0)}% of the US rate. An establishment is one business location with paid employees.</li>
<li><b>The gap is not even.</b> {gap_sentence}</li>
<li><b>Jobs fell while Kentucky and the US grew.</b> Payroll employment in the 31 counties went from {_f(s['emp_region_first'], 0)} in {s['first']} to {_f(s['emp_region_last'], 0)} in {last}, a change of {_f(s['emp_idx']['Eastern KY'] - 100)}%. Kentucky changed by {_f(s['emp_idx']['Kentucky'] - 100)}% and the US by {_f(s['emp_idx']['United States'] - 100)}%. Establishment counts moved the same direction ({_f(s['est_idx']['Eastern KY'] - 100)}% region, {_f(s['est_idx']['Kentucky'] - 100)}% Kentucky, {_f(s['est_idx']['United States'] - 100)}% US).</li>
<li><b>Most businesses are small, about like everywhere else.</b> {_f(sizes.loc['Eastern KY', 'small_share'])}% of establishments in the region have fewer than 20 employees, against {_f(sizes.loc['Kentucky', 'small_share'])}% in Kentucky and {_f(sizes.loc['United States', 'small_share'])}% in the US. The average establishment has {_f(sizes.loc['Eastern KY', 'emp_per_est'])} employees here, {_f(sizes.loc['Kentucky', 'emp_per_est'])} in Kentucky.</li>
<li><b>Most common types.</b> The largest group is {types.iloc[0]['industry'].lower()} ({types.iloc[0]['est']:,.0f} establishments, {_f(types.iloc[0]['share_pct'])}% of the total). Gasoline stations and general merchandise stores, including warehouse clubs and supercenters, take a larger share of establishments here than across the US ({_f(types[types['naics'] == '4471']['lq'].iloc[0], 1)} and {_f(types[types['naics'] == '4523']['lq'].iloc[0], 1)} times the US share).</li>
<li><b>Fewer households have broadband.</b> {_f(acs.loc['Eastern KY', 'broadband_pct'])}% of households in the region report a broadband subscription of any type, against {_f(acs.loc['Kentucky', 'broadband_pct'])}% in Kentucky and {_f(acs.loc['United States', 'broadband_pct'])}% in the US. {_f(acs.loc['Eastern KY', 'no_internet_pct'])}% have no internet access at all. County rates run from {_f(worst['broadband_pct'])}% ({worst['county']}) to {_f(best['broadband_pct'])}% ({best['county']}).</li>
<li><b>Lower incomes.</b> The middle county has a median household income of ${_f(acs.loc['Eastern KY', 'income'], 0)}, against ${_f(acs.loc['Kentucky', 'income'], 0)} for Kentucky and ${_f(acs.loc['United States', 'income'], 0)} for the US. {s['unreliable']} of 31 county estimates have a margin of error over 10% of the estimate, so county rankings are rough.</li>
<li><b>Income and broadband move together across counties</b> (correlation {_f(s['corr'], 2)} across 31 counties). This is an association in one cross-section. The data cannot say which causes which.</li>
</ul>
<p>What this does not show: why the numbers differ, whether any single business is doing well, or anything about the self-employed and farms (County Business Patterns leaves them out). See Caveats.</p></section>

<section class="glass" id="density"><h2>Establishments per 1,000 residents</h2>
<p>Counts come from County Business Patterns {last}. The region total is the plain sum of 31 counties divided by their combined population estimate.</p>
{fig('estab_by_sector.png', f'Establishments per 1,000 residents by 2-digit NAICS sector, {last}. Eastern KY, Kentucky and the US.')}
{fig('county_estab.png', f'All-sector establishments per 1,000 residents in each of the 31 counties, {last}. Orange line is Kentucky, dashed line is the US.')}
{fig('size_mix.png', f'Share of establishments by size class, {last}.')}</section>

<section class="glass" id="jobs"><h2>Employment trends</h2>
<p>Employment in County Business Patterns is the payroll count for the pay period that includes March 12. Both lines start at 100 in 2012.</p>
{fig('employment_trend.png', f'Employment and establishments indexed to 2012 = 100, {s["first"]} to {last}.')}
<div class="caveat">Two things to read with this chart. The 2021 dip in all three lines matches the pandemic years and is not specific to this region. The establishment line for Eastern KY drops in one step between 2016 and 2017. This analysis does not explain that step. It lines up with the switch to NAICS 2017 industry codes in the 2017 data, which may play a part, but that was not tested, so treat the size of the drop with caution.</div>
<h3>By sector, {analysis.SECTOR_BASE_YEAR} to {last}</h3>
<p>Sector employment is only compared from {analysis.SECTOR_BASE_YEAR}, the first year where no county's value is withheld. Among sectors with at least 1,000 jobs in the region, the biggest increases were {sect_up}, and the biggest decreases were {sect_dn}.</p>
{fig('sector_change.png', f'Percent change in employment by sector, {analysis.SECTOR_BASE_YEAR} to {last}.')}
<div class="caveat">Large percentage moves in a sector can come from one employer opening, closing or moving, from noise added by the Census Bureau (see Caveats), or from industry code changes between NAICS versions. This analysis does not separate those.</div></section>

<section class="glass" id="types"><h2>Most common business types</h2>
<p>Ranked by establishment count across the 31 counties, using 4-digit industry groups. "Ratio to US share" divides the group's share of all establishments here by its share nationally. Above 1 means it makes up a bigger slice here, not that there are more of them per resident.</p>
{fig('business_types.png', f'Twelve most common industry groups in Eastern KY, {last}.')}
{type_table}</section>

<section class="glass" id="internet"><h2>Internet subscriptions</h2>
<p>{analysis.ACS_LABEL} estimates, table B28002. "Broadband of any type" includes cellular data plans, so a household with only a phone plan counts. {_f(acs.loc['Eastern KY', 'cellular_only_pct'])}% of households in the region rely on a cellular plan alone ({_f(acs.loc['Kentucky', 'cellular_only_pct'])}% in Kentucky). Region rates are household-weighted sums across the 31 counties.</p>
{fig('broadband.png', f'Share of households with any broadband subscription by county. {analysis.ACS_LABEL}.')}</section>

<section class="glass" id="income"><h2>Median household income</h2>
{fig('income.png', f'Median household income by county with 90% margins of error. {analysis.ACS_LABEL}, 2024 dollars.')}
{fig('income_vs_broadband.png', 'Median household income against broadband subscription rate, one dot per county.')}
<h3>County table</h3>{cty_table}</section>

<section class="glass" id="caveats"><h2>Caveats and limits</h2>
<h3>Suppressed and noisy Census cells</h3>
<p>County Business Patterns protects confidentiality in two ways. Older files (2012 to 2016) withhold employment for many county and sector cells and give only a size range. Newer files publish every cell but add random noise and flag it: G means under 2%, H means 2% to under 5%, J means 5% or more. This analysis treats withheld values as missing, never zero, and adds a regional total only when all 31 counties have a value. Establishment counts are not withheld.</p>
{supp_table}
<p>Because of this, sector-level job changes start in {analysis.SECTOR_BASE_YEAR}. All-sector employment is available for every year.</p>
<h3>Other limits</h3>
<ul>
<li>County Business Patterns counts establishments with paid employees. It excludes the self-employed with no payroll, most farms, railroads, private households and government. Many small businesses in rural counties are in those groups, so the figures understate them.</li>
<li>Establishments are locations, not companies. A chain with 12 stores counts as 12.</li>
<li>Per-resident rates use population estimates, not the number of people able to work or the number of customers who live outside the county.</li>
<li>ACS figures are survey estimates averaged over five years ({analysis.ACS_LABEL}) and carry margins of error. The region "income" is the median of the 31 county medians, which is not the same as the median across all households in the region.</li>
<li>Industry codes changed from NAICS 2012 to 2017 to 2022. Sector comparisons across versions may include reclassification.</li>
<li>"Eastern Kentucky" has no single official boundary. This study uses the five area development districts Big Sandy, Kentucky River, Cumberland Valley, FIVCO and Gateway (31 counties, listed in <code>data/counties.csv</code>). A different definition would give different totals.</li>
<li>The Census Bureau's API now asks for a key, so this study reads the bulk files from www2.census.gov instead. It uses no API key.</li>
<li>This is descriptive. It does not test why any gap exists.</li>
</ul></section>

<section class="glass" id="sources"><h2>Sources</h2>
<p>All files are public and need no account or key. Raw files are downloaded to a local cache and checked against SHA-256 checksums stored in <code>data/checksums.json</code>.</p>
<ul>
<li>County Business Patterns, 2012 to 2023, county, state and national files: <a href="https://www.census.gov/programs-surveys/cbp/data/datasets.html">census.gov/programs-surveys/cbp</a> (files under <code>https://www2.census.gov/programs-surveys/cbp/datasets/</code>).</li>
<li>American Community Survey 2020-2024 5-year, table-based summary files B01003, B19013, B28002: <code>https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/</code>.</li>
<li>Population Estimates, Vintage 2024, county totals: <code>https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv</code>.</li>
<li>CBP NAICS descriptions (NAICS 2017): <code>https://www2.census.gov/programs-surveys/cbp/technical-documentation/reference/naics-descriptions/naics2017.txt</code>.</li>
</ul>
<p>This product uses Census Bureau data but is not endorsed or certified by the Census Bureau.</p></section>
</main>
<footer>Chase Builds &middot; MIT licensed &middot; <a href="https://github.com/chasebuilds/small-business-county-study">source</a></footer>
</body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    (out.parent / "findings.json").write_text(
        json.dumps(
            {
                "estab_per_1000": {g: float(tot[g]) for g in analysis.GEOS},
                "broadband_pct": {g: float(acs.loc[g, "broadband_pct"]) for g in analysis.GEOS},
                "income": {g: float(acs.loc[g, "income"]) for g in analysis.GEOS},
                "emp_change_pct_since_2012": {g: float(s["emp_idx"][g] - 100) for g in analysis.GEOS},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return out
