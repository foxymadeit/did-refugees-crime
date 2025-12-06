from pathlib import Path

# Project root:
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"

# Main processed panel file
PANEL_PATH = PROCESSED_DIR / "panel_2010_2020.csv"

# DID design parameters (can be used later in models)
TREATMENT_YEAR = 2015
PRE_PERIOD_START = 2010
PRE_PERIOD_END = 2014
POST_PERIOD_START = 2016
POST_PERIOD_END = 2020