#!/usr/bin/env python3
"""Paper Table III — Safety-refusal summary by adversarial oracle."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from _common import run_builder
raise SystemExit(run_builder(
    "rq1/scripts/build_tab2_refusal_summary.py",
    ["tab2_refusal_summary.csv", "tab2_refusal_per_iter.csv"],
    "Table III — Safety-refusal summary", "table3_refusal",
    {"tab2_refusal_summary.csv": "table3_refusal_summary.csv",
     "tab2_refusal_per_iter.csv": "table3_refusal_per_iter.csv"},
))
