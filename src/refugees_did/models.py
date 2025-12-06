import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
from statsmodels.regression.linear_model import RegressionResults


# Core DID models

def fit_baseline_did(panel: pd.DataFrame) -> RegressionResults:
    """
    Fit a simple DID model without fixed effects.

    Model:
        crime_rate_per_100k ~ did

    Parameters:
    ------------
    panel: pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'did'

    Returns
    --------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """

    model = smf.ols(
        formula="crime_rate_per_100k ~ did",
        data=panel,
    ).fit(cov_type="HC3")
    return model

def fit_main_did(panel: pd.DataFrame) -> RegressionResults:
    """
    Fit the main DID model with region and year fixed effects.

    Model:
        crime_rate_per_100k ~ did + C(region) + C(year)

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'did'
        - 'region'
        - 'year'

    Returns
    -------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """
    model = smf.ols(
        formula="crime_rate_per_100k ~ did + C(region) + C(year)",
        data=panel,
    ).fit(cov_type="HC3")
    return model


def fit_did_with_covariates(panel: pd.DataFrame) -> RegressionResults:
    """
    Fit a DID model with additional controls and fixed effects.

    Example specification:
        crime_rate_per_100k ~ did
            + ilo_unemployment_rate_pct
            + foreigners_share_pct
            + C(region) + C(year)

    Adjust the covariate names to your actual column names if needed.

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'did'
        - 'ilo_unemployment_rate_pct'
        - 'foreigners_share_pct'
        - 'region'
        - 'year'

    Returns
    -------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """
    formula = """
        crime_rate_per_100k ~ did
        + ilo_unemployment_rate_pct
        + foreigners_share_pct
        + C(region)
        + C(year)
    """

    model = smf.ols(
        formula=formula,
        data=panel,
    ).fit(cov_type="HC3")
    return model



# Event-study model

def fit_event_study(panel: pd.DataFrame, ref_year: int = 2015) -> RegressionResults:
    """
    Fit an event-study model with region FE and year FE interacted with treatment.

    Model (schema):
        crime_rate_per_100k ~ C(region)
                            + C(year, Treatment(reference=ref_year))
                            + C(year, Treatment(reference=ref_year)) : treated

    This allows to extract dynamic treatment effects relative to the reference year.

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'year'
        - 'region'
        - 'treated'
    ref_year : int, default 2015
        Reference year used as k=0 in the event study.

    Returns
    -------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """
    formula = (
        "crime_rate_per_100k ~ "
        "C(region) + "
        f"C(year, Treatment(reference={ref_year})) + "
        f"C(year, Treatment(reference={ref_year})):treated"
    )

    model = smf.ols(
        formula=formula,
        data=panel,
    ).fit(cov_type="HC3")

    return model



# Parallel trends / pretrend


def fit_pretrend_interaction(panel: pd.DataFrame, pre_cutoff_year: int = 2016) -> RegressionResults:
    """
    Test for parallel pre-treatment trends by interacting treatment with a time trend
    in the pre-period only.

    Steps:
    - keep years < pre_cutoff_year (e.g. 2016)
    - create a numeric time variable starting from 0
    - estimate: crime_rate_per_100k ~ treated * year_num + C(region)

    The key coefficient is treated:year_num. If it is not significantly
    different from zero, this supports the parallel trends assumption.

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'year'
        - 'region'
        - 'treated'
    pre_cutoff_year : int, default 2016
        Upper bound (exclusive) for the pre-period.

    Returns
    -------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """
    pre = panel[panel["year"] < pre_cutoff_year].copy()
    pre["year_num"] = pre["year"] - pre["year"].min()

    model = smf.ols(
        formula="crime_rate_per_100k ~ treated * year_num + C(region)",
        data=pre,
    ).fit(cov_type="HC3")

    return model



# Placebo DiD


def fit_placebo_did(panel: pd.DataFrame, fake_treatment_year: int = 2013) -> RegressionResults:
    """
    Fit a placebo DID model by changing the treatment year to a fake year.

    Steps:
    - define fake_post = 1{year >= fake_treatment_year}
    - define fake_did = treated * fake_post
    - estimate: crime_rate_per_100k ~ fake_did + C(region) + C(year)

    A non-significant fake_did coefficient supports the validity
    of the original treatment timing.

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'year'
        - 'region'
        - 'treated'
    fake_treatment_year : int, default 2013
        Year used as a placebo treatment cutoff.

    Returns
    -------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """
    df = panel.copy()

    df["fake_post"] = (df["year"] >= fake_treatment_year).astype(int)
    df["fake_did"] = df["treated"] * df["fake_post"]

    model = smf.ols(
        formula="crime_rate_per_100k ~ fake_did + C(region) + C(year)",
        data=df,
    ).fit(cov_type="HC3")

    return model



# Threshold-based model


def run_did_with_threshold(panel: pd.DataFrame, threshold: float) -> RegressionResults:
    """
    Re-estimate the DID model using an alternative treatment threshold
    on treatment_intensity in year 2016.

    Steps:
    - take treatment_intensity in 2016 by region
    - define treated_alt = 1{treatment_intensity_2016 > threshold}
    - define did_alt = treated_alt * post
    - estimate: crime_rate_per_100k ~ did_alt + C(region) + C(year)

    Parameters
    ----------
    panel : pd.DataFrame
        Must contain:
        - 'crime_rate_per_100k'
        - 'treatment_intensity'
        - 'post'
        - 'year'
        - 'region'
    threshold : float
        Threshold value applied to treatment_intensity in 2016.

    Returns
    -------
    RegressionResults
        Fitted OLS model with robust (HC3) standard errors.
    """
    df = panel.copy()

    # treatment_intensity in 2016 by region
    ti_2016 = (
        df[df["year"] == 2016]
        .set_index("region")["treatment_intensity"]
    )

    treated_regions_alt = (ti_2016 > threshold).astype(int)

    df["treated_alt"] = df["region"].map(treated_regions_alt).fillna(0).astype(int)
    df["did_alt"] = df["treated_alt"] * df["post"]

    model = smf.ols(
        formula="crime_rate_per_100k ~ did_alt + C(region) + C(year)",
        data=df,
    ).fit(cov_type="HC3")

    return model


def run_threshold_grid(panel: pd.DataFrame,thresholds: dict[str, float]) -> pd.DataFrame:
    """
    Run DID models for a grid of thresholds and collect the main effect.

    Parameters
    ----------
    panel : pd.DataFrame
        Panel with treatment_intensity, post, region, year, crime_rate_per_100k.
    thresholds : dict[str, float]
        Mapping from a label (e.g. "p40", "p50", "p60") to a numeric threshold.

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per threshold and:
        - 'name': threshold label
        - 'threshold': numeric threshold
        - 'coef_did_alt': coefficient for did_alt
        - 'se_did_alt': robust standard error
        - 'pvalue_did_alt': p-value
    """
    rows = []

    for name, thr in thresholds.items():
        model = run_did_with_threshold(panel, thr)
        coef = model.params.get("did_alt", np.nan)
        se = model.bse.get("did_alt", np.nan)
        pval = model.pvalues.get("did_alt", np.nan)

        rows.append(
            {
                "name": name,
                "threshold": thr,
                "coef_did_alt": coef,
                "se_did_alt": se,
                "pvalue_did_alt": pval,
            }
        )

    return pd.DataFrame(rows)
