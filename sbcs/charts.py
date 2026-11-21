"""Draw every chart from the analysis tables. One function per chart, PNG output."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import analysis

REGION = "#0f766e"
KY = "#d97706"
US = "#475569"
COLORS = {"Eastern KY": REGION, "Kentucky": KY, "United States": US}
INK = "#2a2019"
GRID = "#d9d2c8"

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _save(fig: plt.Figure, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def short(label: str, width: int = 34) -> str:
    return label if len(label) <= width else label[: width - 1].rstrip() + "..."


def estab_by_sector(data: analysis.Data, out: Path) -> Path:
    df = analysis.estab_per_1000_by_sector(data)
    df = df[df["naics"] != "ALL"].sort_values("Eastern KY")
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(8.6, 7))
    h = 0.27
    for i, g in enumerate(analysis.GEOS):
        ax.barh(y + (1 - i) * h, df[g], height=h, color=COLORS[g], label=g)
    ax.set_yticks(y, [short(s) for s in df["sector"]])
    ax.set_xlabel("Establishments per 1,000 residents")
    ax.set_title("Establishments per 1,000 residents by sector", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, out, "estab_by_sector.png")


def county_estab(data: analysis.Data, out: Path) -> Path:
    df = analysis.county_total_estab(data)
    pops = analysis.population(data)
    ky = analysis.geo_rows(data, analysis.LATEST_CBP, "ALL")["Kentucky"]["est"] / pops["Kentucky"] * 1000
    us = (
        analysis.geo_rows(data, analysis.LATEST_CBP, "ALL")["United States"]["est"]
        / pops["United States"]
        * 1000
    )
    fig, ax = plt.subplots(figsize=(8.6, 7))
    ax.barh(df["county"], df["est_per_1000"], color=REGION)
    ax.axvline(ky, color=KY, lw=2, label=f"Kentucky ({ky:.1f})")
    ax.axvline(us, color=US, lw=2, ls="--", label=f"United States ({us:.1f})")
    ax.set_xlabel("Establishments per 1,000 residents")
    ax.set_title("All-sector establishments per 1,000 residents, by county", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, out, "county_estab.png")


def employment_trend(data: analysis.Data, out: Path) -> Path:
    df = analysis.totals_trend(data)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.2), sharey=False)
    for ax, col, title in (
        (axes[0], "emp_idx", "Employment (March payroll)"),
        (axes[1], "est_idx", "Establishments"),
    ):
        for g in analysis.GEOS:
            sub = df[df["geo"] == g]
            ax.plot(sub["year"], sub[col], color=COLORS[g], lw=2.2, label=g, marker="o", ms=3)
        ax.axhline(100, color=GRID, lw=1)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_ylabel("Index, 2012 = 100")
        ax.set_xticks(sorted(df["year"].unique())[::2])
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("Change since 2012, all sectors", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, out, "employment_trend.png")


def sector_change(data: analysis.Data, out: Path, min_emp: int = 1000) -> Path:
    df = analysis.sector_emp_change(data)
    df = df[df["emp_latest"] >= min_emp].sort_values("Eastern KY")
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    h = 0.27
    for i, g in enumerate(analysis.GEOS):
        ax.barh(y + (1 - i) * h, df[g], height=h, color=COLORS[g], label=g)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(y, [short(s) for s in df["sector"]])
    ax.set_xlabel(f"% change in employment, {analysis.SECTOR_BASE_YEAR} to {analysis.LATEST_CBP}")
    ax.set_title(
        f"Employment change by sector (Eastern KY sectors with {min_emp:,}+ jobs)",
        loc="left",
        fontweight="bold",
    )
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, out, "sector_change.png")


def broadband(data: analysis.Data, out: Path) -> Path:
    df = analysis.acs_county(data)
    summ = analysis.acs_summary(data).set_index("geo")
    fig, ax = plt.subplots(figsize=(8.6, 7))
    ax.barh(df["county"], df["broadband_pct"], color=REGION)
    ax.axvline(summ.loc["Kentucky", "broadband_pct"], color=KY, lw=2, label="Kentucky")
    ax.axvline(summ.loc["United States", "broadband_pct"], color=US, lw=2, ls="--", label="United States")
    ax.set_xlim(60, 100)
    ax.set_xlabel("% of households with a broadband subscription of any type")
    ax.set_title(f"Household broadband, by county ({analysis.ACS_LABEL})", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, out, "broadband.png")


def income(data: analysis.Data, out: Path) -> Path:
    df = analysis.acs_county(data).sort_values("income")
    summ = analysis.acs_summary(data).set_index("geo")
    fig, ax = plt.subplots(figsize=(8.6, 7))
    colors = [("#99b8b4" if u else REGION) for u in df["income_unreliable"]]
    ax.barh(df["county"], df["income"], xerr=df["income_moe"], color=colors, ecolor=INK, capsize=2)
    ax.axvline(summ.loc["Kentucky", "income"], color=KY, lw=2, label="Kentucky")
    ax.axvline(summ.loc["United States", "income"], color=US, lw=2, ls="--", label="United States")
    ax.set_xlabel("Median household income, dollars (bars show the 90% margin of error)")
    ax.set_title(
        "Median household income, by county (pale bars: margin of error over 10% of estimate)",
        loc="left",
        fontweight="bold",
        fontsize=10,
    )
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, out, "income.png")


def income_vs_broadband(data: analysis.Data, out: Path) -> Path:
    df = analysis.acs_county(data)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.scatter(df["income"], df["broadband_pct"], color=REGION, s=36)
    for _, r in df.iterrows():
        if r["broadband_pct"] < 80 or r["income"] > 60000 or r["income"] < 31000:
            ax.annotate(r["county"], (r["income"], r["broadband_pct"]), fontsize=8, xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("Median household income, dollars")
    ax.set_ylabel("% households with broadband")
    ax.set_title("Income and broadband, 31 counties (an association, not a cause)", loc="left", fontweight="bold", fontsize=10)
    return _save(fig, out, "income_vs_broadband.png")


def business_types(data: analysis.Data, out: Path) -> Path:
    df = analysis.business_types(data).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    ax.barh([short(s, 40) for s in df["industry"]], df["share_pct"], color=REGION, label="Eastern KY")
    ax.scatter(df["us_share_pct"], range(len(df)), color=US, zorder=3, label="US share", marker="D", s=26)
    ax.set_xlabel("% of all establishments")
    ax.set_title(
        f"Twelve most common industry groups, Eastern KY, {analysis.LATEST_CBP}",
        loc="left",
        fontweight="bold",
    )
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, out, "business_types.png")


def size_mix(data: analysis.Data, out: Path) -> Path:
    df = analysis.size_mix(data).set_index("geo")
    cols = [("n_lt5", "Under 5"), ("n5_9", "5 to 9"), ("n10_19", "10 to 19"), ("n20_plus", "20 or more")]
    palette = ["#0f766e", "#5eaaa4", "#a8cfcb", "#d97706"]
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    left = np.zeros(len(df))
    for (col, name), color in zip(cols, palette, strict=True):
        vals = df[col].to_numpy()
        ax.barh(df.index, vals, left=left, color=color, label=name)
        for i, v in enumerate(vals):
            ax.text(left[i] + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=9, color="white" if col in ("n_lt5", "n20_plus") else INK)
        left += vals
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of establishments, by employees per establishment")
    ax.set_title(f"Establishment size mix, {analysis.LATEST_CBP}", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    return _save(fig, out, "size_mix.png")


def build_all(data: analysis.Data, out: Path) -> list[Path]:
    makers = [
        estab_by_sector,
        county_estab,
        employment_trend,
        sector_change,
        broadband,
        income,
        income_vs_broadband,
        business_types,
        size_mix,
    ]
    return [m(data, out) for m in makers]


def frame_to_records(df: pd.DataFrame) -> list[dict]:
    return df.to_dict("records")
