"""§6.3 — named Delhi landmark checks. The most persuasive artefact in the
build: a Delhi-native panelist can verify the engine's output against their
own knowledge of these locations in about ten seconds.

Each landmark also doubles as an "anchor hex" for SyntheticSource: since
there's no guarantee real Dynamic World data has landed by demo time, we pin
these specific named cells to the archetype the location is known to exhibit,
clearly labelled SIMULATED DATA throughout the viewer. The engine still has
to recover the correct lifecycle stage from noisy synthetic observations —
this checks the fitting/tiering/classification pipeline, not the data.
"""

from __future__ import annotations

import h3
import pandas as pd

# Dynamic-archetype landmarks get hand-tuned (not randomly sampled) (K, r, t0)
# with a comfortable safety margin from the nearest classification boundary
# (e.g. Dwarka/Rohini sit at ~75-82% of K by t_eval, well clear of the 90%
# Saturated cutoff) so the demo table is stable across reruns rather than
# occasionally flipping when noise happens to land near a boundary — the
# fitting pipeline is still run on noisy synthetic observations generated
# from these parameters, it's only the ground truth that's fixed.
LANDMARKS = [
    dict(name="Karol Bagh", lat=28.6519, lon=77.1909, archetype="saturated_static",
         expected=["Saturated"]),
    dict(name="Lajpat Nagar", lat=28.5677, lon=77.2433, archetype="saturated_static",
         expected=["Saturated"]),
    dict(name="Dwarka Sector 21", lat=28.5521, lon=77.0580, archetype="maturing",
         expected=["Maturing"], K=0.85, r=0.30, t0=2021.0),
    dict(name="Rohini Sector 24", lat=28.7350, lon=77.1050, archetype="maturing",
         expected=["Maturing"], K=0.90, r=0.28, t0=2019.5),
    dict(name="Narela", lat=28.8530, lon=77.0920, archetype="accelerating",
         expected=["Emerging", "Accelerating"], K=0.75, r=0.80, t0=2026.5),
    dict(name="Bawana", lat=28.7990, lon=77.0350, archetype="emerging",
         expected=["Emerging", "Accelerating"], K=0.70, r=0.50, t0=2028.5),
    dict(name="Yamuna floodplain (Zone O ref)", lat=28.6420, lon=77.2560, archetype="undeveloped",
         expected=None, flag_nonzero_velocity=True),
]


def get_anchor_overrides(t_eval: float, resolution: int = 9) -> dict:
    """Resolves each landmark to its H3 cell and returns the (archetype, K, r,
    t0) that will be baked into that specific cell when SyntheticSource
    generates the demo grid."""
    overrides = {}
    for lm in LANDMARKS:
        cell = h3.latlng_to_cell(lm["lat"], lm["lon"], resolution)
        override = {"archetype": lm["archetype"]}
        if lm["archetype"] not in ("undeveloped", "saturated_static"):
            override.update(K=lm["K"], r=lm["r"], t0=lm["t0"])
        overrides[cell] = override
    return overrides


def run_facevalidity(hex_metrics: pd.DataFrame, resolution: int = 9) -> tuple[list[dict], str]:
    """Returns (results, markdown_table)."""
    indexed = hex_metrics.set_index("h3_index")
    results = []

    for lm in LANDMARKS:
        cell = h3.latlng_to_cell(lm["lat"], lm["lon"], resolution)
        if cell not in indexed.index:
            results.append(dict(
                name=lm["name"], h3_index=cell, expected=lm.get("expected"),
                actual=None, velocity=None, passed=False,
                note="hex not found in hex_metrics output",
            ))
            continue

        row = indexed.loc[cell]
        actual_lifecycle = row.get("lifecycle")
        velocity = row.get("velocity_2026")

        if lm.get("flag_nonzero_velocity"):
            threshold = 0.005  # fraction/year
            flagged = bool(pd.notna(velocity) and abs(velocity) > threshold)
            results.append(dict(
                name=lm["name"], h3_index=cell, expected="velocity ~ 0",
                actual=f"velocity={velocity:.4f}" if pd.notna(velocity) else "n/a",
                velocity=velocity, passed=not flagged,
                note="FLAGGED: non-zero velocity on floodplain" if flagged else "OK: no significant growth",
            ))
            continue

        passed = actual_lifecycle in lm["expected"]
        results.append(dict(
            name=lm["name"], h3_index=cell, expected=" / ".join(lm["expected"]),
            actual=actual_lifecycle, velocity=velocity, passed=passed, note="",
        ))

    n_pass = sum(1 for r in results if r["passed"])
    lines = [
        "## Face validity — named Delhi landmarks",
        "",
        f"**{n_pass}/{len(results)} passed.**",
        "",
        "| Location | H3 cell | Expected | Actual | Velocity (frac/yr) | Result | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        vel = f"{r['velocity']:.4f}" if isinstance(r["velocity"], (int, float)) and pd.notna(r["velocity"]) else "n/a"
        lines.append(
            f"| {r['name']} | `{r['h3_index']}` | {r['expected']} | {r['actual']} | {vel} | {mark} | {r['note']} |"
        )
    markdown = "\n".join(lines)
    return results, markdown
