"""filters.py — denominator filters and verdict-aggregation helpers."""
from typing import Optional


def iter_0_normal_scenarios(classifications: dict, all_scenarios: set[tuple[str,str]]) -> set[tuple[str,str]]:
    """Filter to scenarios with classification[(sk,cat,0)] == 'normal'.
    classifications is dict[(skill, cat_folder, iter)] -> str."""
    return {(sk, cat) for (sk, cat) in all_scenarios
            if classifications.get((sk, cat, 0)) == "normal"}


def last_good_iter(classifications: dict, sk: str, cat: str, max_iter: int) -> Optional[int]:
    """Return the highest iter K ∈ [0, max_iter] with classification[(sk,cat,K)] == 'normal'.
    None if no such iter exists."""
    best = None
    for it in range(max_iter + 1):
        if classifications.get((sk, cat, it)) == "normal":
            best = it
    return best


def is_iter_normal(classifications: dict, sk: str, cat: str, it: int) -> bool:
    return classifications.get((sk, cat, it)) == "normal"
