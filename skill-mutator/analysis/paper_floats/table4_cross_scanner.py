#!/usr/bin/env python3
"""Paper Table IV — Cross-scanner detection-rate matrix."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from _common import run_builder
raise SystemExit(run_builder(
    "rq1/scripts/build_tab1_cross_matrix.py",
    ["tab1_cross_matrix.csv", "tab1_cross_matrix.tex"],
    "Table IV — Cross-scanner detection", "table4_cross_scanner",
    {"tab1_cross_matrix.csv": "table4_cross_scanner.csv",
     "tab1_cross_matrix.tex": "table4_cross_scanner.tex"},
))
