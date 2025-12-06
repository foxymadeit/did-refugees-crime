from __future__ import annotations

from pathlib import Path
from typing import Optional, Union, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.regression.linear_model import RegressionResults
import re



# Parallel trends visualization


def compute_parallel_trends_data(
    panel: pd.DataFrame,
    outcome: str = "crime_rate_per_100k",
) -> pd.DataFrame:
    """
    Aggregate outcome by year and treatment status.

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'year'
        - 'treated'
        - outcome column (default: crime_rate_per_100k)
    outcome : str
        Outcome column name.

    Returns
    -------
    pd.DataFrame
        Columns:
        - year
        - treated
        - mean
    """
    # Check for missing data from panel
    required = {"year", "treated", outcome}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"panel is missing required columns: {missing}")

    grouped = (
        panel
        .groupby(["year", "treated"], as_index=False)[outcome]
        .mean()
        .rename(columns={outcome: "mean"})
    )

    return grouped


def plot_parallel_trends(
    panel: pd.DataFrame,
    outcome: str = "crime_rate_per_100k",
    ax: Optional[plt.Axes] = None,
    save_path: Optional[Union[str, Path]] = None,
) -> plt.Axes:
    """
    Plot parallel trends for treated vs control groups.

    Parameters
    ----------
    panel : pd.DataFrame
        Panel with columns:
        - 'year'
        - 'treated' (0/1)
        - outcome
    outcome : str, default "crime_rate_per_100k"
        Outcome variable to plot.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on. If None, a new figure is created.
    save_path : str or Path, optional
        If provided, the plot is saved to this path.

    Returns
    -------
    matplotlib.axes.Axes
        Axis with the plot.
    """
    df = compute_parallel_trends_data(panel, outcome=outcome)

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))


    for treated_flag, label in [(0, "Control regions"), (1, "Treated regions")]:
        sub = df[df["treated"] == treated_flag].copy()
        if sub.empty:
            continue

        years = sub["year"].values
        mean = sub["mean"].values

        ax.plot(years, mean, marker="o", linestyle="-", label=label)

    ax.axvline(2015, linestyle="--", linewidth=1, label="Treatment year (2015)")
    ax.set_xlabel("Year")
    ax.set_ylabel(outcome)
    ax.set_title("Parallel trends: treated vs control")
    ax.legend()
    ax.grid(True, alpha=0.3)

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight")

    return ax


# Event-study extraction



# Pattern to pick only event-study interaction terms:
#   C(year, Treatment(reference=2015))[2018]:treated

_EVENT_PATTERN = re.compile(
    r"C\(year, Treatment\(reference=\d+\)\)\[(?P<year>\d+)\]:treated"
)


def build_event_study_table(
    event_model: RegressionResults,
    ref_year: int,
) -> pd.DataFrame:
    """
    Build an event-study table from a fitted OLS model.

       The function:
    - selects only parameters of the form
        C(year, Treatment(reference=...))[YYYY]:treated
    - extracts:
        * calendar year (YYYY)
        * relative year (YYYY - ref_year)
        * coefficient (coef)
        * standard error (se)
        * 95% confidence interval from model.conf_int()

    Parameters
    ----------
    event_model : RegressionResults
        Fitted model from fit_event_study().
    ref_year : int
        Reference year used in the Treatment(reference=...)

    Returns
    -------
    pd.DataFrame
        Columns:
        - year: calendar year
        - rel_year: year - ref_year
        - coef: estimated effect
        - se: standard error
        - ci_low, ci_high: 95% CI bounds
    """
    # All coefficients and standard errors
    params = event_model.params
    se_series = event_model.bse
    pvals = event_model.pvalues

    # Confidence intervals for all parameters
    conf = event_model.conf_int()
    conf.columns = ["ci_low", "ci_high"]

    rows = []

    for name, coef in params.items():
        match = _EVENT_PATTERN.match(name)
        if not match:
            continue

        year = int(match.group("year"))
        se = se_series.get(name, np.nan)
        pvalue = pvals.get(name, np.nan)

        if name in conf.index:
            ci_low = conf.loc[name, "ci_low"]
            ci_high = conf.loc[name, "ci_high"]
        else:
            ci_low = np.nan
            ci_high = np.nan
        
        rel_year = year - ref_year

        rows.append(
            {
                "year": year,
                "rel_year": rel_year,
                "coef": coef,
                "se": se,
                "pvalue": pvalue,
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
        )

    if not rows:
        raise ValueError(
            "No event-study coefficients found. "
            "Check that fit_event_study() was used to estimate the model."
        )

    df = pd.DataFrame(rows)

    # Add reference year with effect = 0 for plotting
    if not (df["year"] == ref_year).any():
        ref_row = {
            "year": ref_year,
            "rel_year": 0,
            "coef": 0.0,
            "se": np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
        }
        df = pd.concat([df, pd.DataFrame([ref_row])], ignore_index=True)

    df = df.sort_values("rel_year").reset_index(drop=True)
    df["pvalue"] = df["pvalue"].round(3)
    return df


def plot_event_study(
    event_model: RegressionResults,
    ref_year: int,
    ax: Optional[plt.Axes] = None,
    save_path: Optional[Union[str, Path]] = None,
) -> plt.Axes:
    """
    Plot event-study coefficients (dynamic DID effects) with shaded 95% CIs.

    Parameters
    ----------
    event_model : RegressionResults
        Fitted model from fit_event_study().
    ref_year : int
        Reference year used for Treatment(reference=...).
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on. If None, a new figure is created.
    save_path : str or Path, optional
        If provided, the plot is saved to this path.

    Returns
    -------
    matplotlib.axes.Axes
        Axis with the event-study plot.
    """
    df = build_event_study_table(event_model, ref_year=ref_year)

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))


    
    # Mark horizontal line at 0 to show "zero effect" line
    ax.axhline(0.0, linestyle="--", linewidth=1, alpha=0.7)

    # Mark reference year at 0
    ax.axvline(0.0, linestyle=":", linewidth=1, alpha=0.7)
    
    x = df['rel_year'].values
    y = df['coef'].values

    mask_ci = df["ci_low"].notna() & df["ci_high"].notna()
    x_ci = df.loc[mask_ci, "rel_year"].values
    ci_low = df.loc[mask_ci, "ci_low"].values
    ci_high = df.loc[mask_ci, "ci_high"].values

    ax.plot(x, y, marker='o', linestyle='-', label='Event-study effect')

    if len(x_ci) > 0:
        ax.fill_between(x_ci, ci_low, ci_high, alpha=0.2)


    ax.set_xlabel(f"Years relative to {ref_year}")
    ax.set_ylabel("Effect on crime_rate_per_100k")
    ax.set_title("Event-study: dynamic treatment effects")
    ax.grid(True, alpha=0.3)


    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight")

    return ax


def compute_treatment_intensity_distribution(
    panel: pd.DataFrame,
    year: int = 2016,
    intensity_col: str = "treatment_intensity",
) -> Tuple[pd.DataFrame, float]:
    """
    Prepare data for plotting the distribution of treatment intensity
    in a given year.

    Parameters
    ----------
    panel : pd.DataFrame
        Panel with at least:
        - 'year'
        - intensity_col (default: 'treatment_intensity')
        - 'treated' (optional, but useful for labeling)
    year : int, default 2016
        Year in which the treatment intensity is evaluated.
    intensity_col : str, default 'treatment_intensity'
        Column name with treatment intensity values.

    Returns
    -------
    df_year : pd.DataFrame
        Subset for the given year with columns:
        - 'region' (if present)
        - intensity_col
        - 'treated' (if present)
    threshold : float
        Median treatment intensity in that year
    """
    required = {"year", intensity_col}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"panel is missing required columns: {missing}")

    # Takes only required year
    cols = ["year", intensity_col]
    if "region" in panel.columns:
        cols.append("region")
    if "treated" in panel.columns:
        cols.append("treated")

    df_year = panel.loc[panel["year"] == year, cols].copy()
    df_year = df_year.dropna(subset=[intensity_col])

    if df_year.empty:
        raise ValueError(f"No rows found for year {year} with non-null {intensity_col}.")

    threshold = df_year[intensity_col].median()

    return df_year, float(threshold)


def plot_treatment_intensity(
    panel: pd.DataFrame,
    year: int = 2016,
    intensity_col: str = "treatment_intensity",
    save_path: Path | None = None,
    ) -> plt.Axes:

    """
    Lollipop plot visualizing treatment intensity by region in a given year.

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'region'
        - 'year'
        - 'intensity_col'
    year : int
        Year from which treatment intensity is taken (default = 2016).
    save_path : Path, optional
        If provided, saves figure to this path.

    Returns
    -------
    matplotlib.axes.Axes
    """
    df, median_thr = compute_treatment_intensity_distribution(
        panel,
        year=year,
        intensity_col=intensity_col,
    )


    df = df.sort_values("treatment_intensity")


    colors = df["treated"].map({0: "#4C72B0", 1: "#DD8452"})

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hlines(
        y=df["region"],
        xmin=0,
        xmax=df["treatment_intensity"],
        color="gray",
        alpha=0.5,
        linewidth=1.5,
    )

    ax.scatter(
        df["treatment_intensity"],
        df["region"],
        s=80,
        c=colors,
        label="Regions",
    )


    ax.axvline(
        median_thr,
        color="black",
        linestyle="--",
        linewidth=1.3,
        label=f"Median threshold = {int(median_thr)}",
    )


    ax.set_title(f"Treatment intensity by region in {year}", fontsize=14)
    ax.set_xlabel("Treatment intensity", fontsize=12)
    ax.set_ylabel("Region", fontsize=12)
    ax.grid(axis="x", alpha=0.3)

    ax.legend(loc="lower right")

    plt.tight_layout()

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight")

    return ax
