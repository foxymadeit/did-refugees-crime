import pandas as pd
from .config import PANEL_PATH

def add_crime_rate_if_missing(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure 'crime_rate_per_100k' exists in the panel.

    If the column is missing, it is computed from:
    - 'total_cases'
    - 'population_total'

    Expects the following minimum:
    - 'total_cases'
    - 'population_total'

    Returns
    --------
    pd.DataFrame
        A copy of the input with the new crime_rate_per_100k columns.
    """
    df = panel.copy()

    if "crime_rate_per_100k" not in df.columns:
        df["crime_rate_per_100k"] = (
            df["total_cases"] / df["population_total"] * 100_000
        )

    return df

def add_treatment_variables(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Add DID design variables to the panel dataframe:

    - 'treatment_intensity': Δ foreigners_total by region
    - 'treated': 1 if a region's intensity in 2016 is above the median threshold
    - 'post': 1 if year >= 2016
    - 'did': treated*post

    Expects the following columns:
    - 'year'
    - 'region'
    - 'foreigners_total'

    Returns
    --------
    pd.DataFrame
        A copy of the input with the new DID variables
    """
    df = panel.copy()

    # Change in the number of foreign residents by region over time
    df["treatment_intensity"] = df.groupby("region")["foreigners_total"].diff()

    # Threshold based on the distribution of treatment_intensity in 2016
    threshold = df.loc[df['year'] == 2016, 'treatment_intensity'].median().astype(int)

    treated_regions = (
        df.loc[df['year'] == 2016]
        .assign(treated=lambda d: d['treatment_intensity'] > threshold)
        .set_index('region')['treated']
    )

    # Map region > treated flag
    df['treated'] = df['region'].map(treated_regions).fillna(0).astype(int)

    # Post-period indicator
    df['post'] = (df['year'] >= 2016).astype(int)

    # DID interaction
    df['did'] = df['treated'] * df['post']

    return df

def prepare_analysis_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the main analysis panel:
    - add DID design variables (treated, post, did)

    Parameters
    -----------
    panel: pd.DataFrame
        Raw panel with at least:
        'total_cases', 'crime_rate_per_100k', 'year', 'region', 'foreigners_total'

    Returns
    ----------
    pd.DataFrame
        Prepared panel ready for modeling and plotting.
    """
    df = panel.copy()
    df = add_crime_rate_if_missing(df)
    df = add_treatment_variables(df)
    return df
