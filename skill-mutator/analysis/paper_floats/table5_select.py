#!/usr/bin/env python3
"""Paper Table V — detection for select vs no-select mutation."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from _common import run_builder
raise SystemExit(run_builder(
    "rq2/scripts/build_tab_select_vs_noselect.py",
    ["tab_select_vs_noselect.csv"],
    "Table V — select vs no-select", "table5_select",
    {"tab_select_vs_noselect.csv": "table5_select_vs_noselect.csv"},
))
