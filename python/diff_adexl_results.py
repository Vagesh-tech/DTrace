#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DTrace
diff_adexl_results.py

Purpose
-------
Compare parsed ADE XL result JSON files and report simulation changes
between design iterations.

Responsibilities
----------------
- Load parsed ADE XL result JSON files
- Compare nominal values
- Compare corner values
- Detect PASS/FAIL transitions
- Identify worst-corner movement
- Rank result changes by mathematical magnitude

Design Principle
----------------
DTrace records what changed. It does not decide what is important.

There are no metric-specific thresholds and no circuit-specific rules.
Any value change is reported. Status transitions are classified only
from PASS/FAIL/NEAR labels.

Notes
-----
- Python 2.6 compatible
- Corner matching uses (process, temperature), not column position
- Intended to be used standalone or imported by dtrace.py
"""

import json
import os
import sys
import re
import glob


# =====================================================================
# User configuration
# =====================================================================
#
# Used only when no explicit file paths are provided.
#
RESULTS_DIR = "./design_tracker/adexl_results"


# =====================================================================
# Loading and path resolution
# =====================================================================

def load_result_json(path):
    """
    Load one parsed ADE XL result JSON file.
    """
    if not os.path.isfile(path):
        raise IOError("Result JSON not found: {0}".format(path))

    data_file = open(path, "r")
    try:
        raw = data_file.read()
    finally:
        data_file.close()

    if not raw.strip():
        raise ValueError("Result JSON is empty: {0}".format(path))

    try:
        return json.loads(raw)
    except ValueError as error:
        raise ValueError("Invalid JSON in {0}: {1}".format(path, error))


def find_result_jsons(results_dir):
    """
    Find parsed ADE XL result JSON files in results_dir.
    """
    pattern = os.path.join(results_dir, "adexl_results_*.json")
    files = glob.glob(pattern)

    def sort_key(path):
        match = re.search(r"adexl_results_(\d+)\.json", os.path.basename(path))
        if match:
            return int(match.group(1))
        return -1

    return sorted(files, key=sort_key)


def resolve_paths(args):
    """
    Resolve command-line arguments into previous/current result paths.

    Supported modes:
        diff_adexl_results.py
        diff_adexl_results.py --full
        diff_adexl_results.py 10 13
        diff_adexl_results.py 10 13 --full
        diff_adexl_results.py prev.json curr.json
        diff_adexl_results.py prev.json curr.json --full
        diff_adexl_results.py --results-dir <dir>
    """
    full_mode = "--full" in args
    clean_args = [arg for arg in args if arg != "--full"]

    results_dir = RESULTS_DIR

    if "--results-dir" in clean_args:
        idx = clean_args.index("--results-dir")

        if idx + 1 >= len(clean_args):
            raise ValueError("--results-dir requires a directory path.")

        results_dir = clean_args[idx + 1]
        clean_args = clean_args[:idx] + clean_args[idx + 2:]

    if not clean_args:
        files = find_result_jsons(results_dir)

        if len(files) < 2:
            raise ValueError(
                "Need at least 2 result JSONs in {0}.\n"
                "Run parse_adexl.py first or provide explicit JSON paths.".format(
                    results_dir
                )
            )

        return files[-2], files[-1], full_mode

    if len(clean_args) == 2:
        try:
            prev_num = int(clean_args[0])
            curr_num = int(clean_args[1])

            prev_path = os.path.join(
                results_dir,
                "adexl_results_{0:03d}.json".format(prev_num)
            )
            curr_path = os.path.join(
                results_dir,
                "adexl_results_{0:03d}.json".format(curr_num)
            )

            return prev_path, curr_path, full_mode

        except ValueError:
            return clean_args[0], clean_args[1], full_mode

    raise ValueError(
        "Usage:\n"
        "  python diff_adexl_results.py [--full]\n"
        "  python diff_adexl_results.py <prev_run> <curr_run> [--full]\n"
        "  python diff_adexl_results.py <prev.json> <curr.json> [--full]\n"
        "  python diff_adexl_results.py --results-dir <dir> [--full]"
    )


# =====================================================================
# Lookup helpers
# =====================================================================

def metric_lookup(results_list):
    """
    Build output-name keyed metric lookup.
    """
    lookup = {}

    for result in results_list:
        output = (result.get("output", "") or "").strip()

        if output:
            lookup[output] = result

    return lookup


def corner_lookup(corners_list):
    """
    Build semantic corner lookup using (process, temperature).
    """
    lookup = {}

    for corner in corners_list:
        key = (
            (corner.get("process", "") or "").strip(),
            (corner.get("temperature", "") or "").strip(),
        )
        lookup[key] = corner

    return lookup


def try_float(value):
    """
    Convert string to float when possible.
    """
    try:
        return float((value or "").strip())
    except (ValueError, TypeError):
        return None


def compute_delta(prev_str, curr_str):
    """
    Compute numeric delta string when both values are numeric.
    """
    prev_float = try_float(prev_str)
    curr_float = try_float(curr_str)

    if prev_float is None or curr_float is None:
        return None

    delta = curr_float - prev_float
    sign = "+" if delta >= 0 else ""

    return "{0}{1:.4g}".format(sign, delta)


def get_spec_direction(spec_str):
    """
    Infer whether a specification is minimize-type or maximize-type.

    Example:
        < 100u  -> minimize
        > 60    -> maximize
    """
    spec = (spec_str or "").strip()

    if spec.startswith("<"):
        return "minimize"

    if spec.startswith(">"):
        return "maximize"

    return "unknown"


def find_worst_corner(corners_list, spec_str):
    """
    Find worst corner using spec direction.

    This is mathematical only. It does not apply analog-domain judgement.
    """
    direction = get_spec_direction(spec_str)
    numeric = []

    for corner in corners_list:
        value = try_float(corner.get("value", ""))

        if value is not None:
            numeric.append((value, corner))

    if not numeric:
        return None, None

    if direction == "minimize":
        worst = max(numeric, key=lambda item: item[0])
    elif direction == "maximize":
        worst = min(numeric, key=lambda item: item[0])
    else:
        worst = max(numeric, key=lambda item: abs(item[0]))

    return worst[0], worst[1]


# =====================================================================
# Status and ranking helpers
# =====================================================================

def classify_status_change(prev_pf, curr_pf):
    """
    Classify PASS/FAIL/NEAR transitions.
    """
    prev = (prev_pf or "").lower()
    curr = (curr_pf or "").lower()

    if prev == curr:
        return "same"

    if prev == "pass" and curr == "fail":
        return "regression"

    if prev == "fail" and curr == "pass":
        return "improvement"

    if prev == "pass" and curr == "near":
        return "regression"

    if prev == "near" and curr == "fail":
        return "regression"

    if prev == "fail" and curr == "near":
        return "improvement"

    if prev == "near" and curr == "pass":
        return "improvement"

    return "near_change"


def status_label(pass_fail):
    """
    Format pass/fail status.
    """
    if pass_fail:
        return pass_fail.upper()

    return "---"


def compute_impact_score(entry):
    """
    Rank entries by magnitude of worst-corner change.

    Status changes rank above value-only changes.
    This ranking is mathematical and intentionally domain-agnostic.
    """
    status = entry.get("status_change", "same")

    if status == "regression":
        base = 10000.0
    elif status == "improvement":
        base = 5000.0
    else:
        base = 0.0

    prev_float = entry.get("prev_worst_float")
    curr_float = entry.get("curr_worst_float")

    if (
        prev_float is not None and
        curr_float is not None and
        abs(prev_float) > 1e-30
    ):
        return base + abs((curr_float - prev_float) / prev_float) * 100.0

    if prev_float is not None and curr_float is not None:
        return base + abs(curr_float - prev_float)

    return base


def format_pct(prev_float, curr_float):
    """
    Format percentage change relative to previous value.
    """
    if (
        prev_float is None or
        curr_float is None or
        abs(prev_float) < 1e-30
    ):
        return ""

    pct = (curr_float - prev_float) / abs(prev_float) * 100.0
    sign = "+" if pct >= 0 else ""

    return "({0}{1:.1f}%)".format(sign, pct)


def corner_label(corner_dict):
    """
    Format corner label.
    """
    if not corner_dict:
        return "?"

    return "{0} {1}C".format(
        corner_dict.get("process", "?"),
        corner_dict.get("temperature", "?")
    )


# =====================================================================
# Diff engine
# =====================================================================

def diff_results(prev_data, curr_data):
    """
    Compare two parsed ADE XL result JSON objects.
    """
    prev_metrics = metric_lookup(prev_data.get("results", []))
    curr_metrics = metric_lookup(curr_data.get("results", []))

    all_outputs = sorted(
        set(list(prev_metrics.keys()) + list(curr_metrics.keys()))
    )

    regressions = []
    improvements = []
    value_changes = []
    no_changes = []
    new_metrics = []
    removed_metrics = []

    for output in all_outputs:
        if not output:
            continue

        if output not in prev_metrics:
            new_metrics.append(output)
            continue

        if output not in curr_metrics:
            removed_metrics.append(output)
            continue

        prev_entry = prev_metrics[output]
        curr_entry = curr_metrics[output]

        prev_pf = (prev_entry.get("pass_fail") or "").lower()
        curr_pf = (curr_entry.get("pass_fail") or "").lower()

        status_change = classify_status_change(prev_pf, curr_pf)

        prev_nominal = prev_entry.get("nominal", "")
        curr_nominal = curr_entry.get("nominal", "")

        spec = curr_entry.get("spec", "") or prev_entry.get("spec", "")

        prev_corners_list = prev_entry.get("corners", [])
        curr_corners_list = curr_entry.get("corners", [])

        prev_corners = corner_lookup(prev_corners_list)
        curr_corners = corner_lookup(curr_corners_list)

        all_corner_keys = sorted(
            set(list(prev_corners.keys()) + list(curr_corners.keys())),
            key=lambda key: (key[0], key[1])
        )

        changed_corners = []

        for corner_key in all_corner_keys:
            process, temperature = corner_key

            prev_corner = prev_corners.get(corner_key)
            curr_corner = curr_corners.get(corner_key)

            if prev_corner is None or curr_corner is None:
                continue

            prev_value = prev_corner.get("value", "")
            curr_value = curr_corner.get("value", "")

            if prev_value == curr_value:
                continue

            changed_corners.append({
                "process":     process,
                "temperature": temperature,
                "prev_val":    prev_value,
                "curr_val":    curr_value,
                "delta_str":   compute_delta(prev_value, curr_value),
            })

        prev_worst_float, prev_worst_corner = find_worst_corner(
            prev_corners_list,
            spec
        )
        curr_worst_float, curr_worst_corner = find_worst_corner(
            curr_corners_list,
            spec
        )

        if (
            status_change == "same" and
            not changed_corners and
            prev_nominal == curr_nominal
        ):
            no_changes.append(output)
            continue

        entry = {
            "output":            output,
            "spec":              spec,
            "prev_pf":           prev_pf,
            "curr_pf":           curr_pf,
            "status_change":     status_change,
            "prev_nominal":      prev_nominal,
            "curr_nominal":      curr_nominal,
            "changed_corners":   changed_corners,
            "prev_worst_float":  prev_worst_float,
            "prev_worst_corner": prev_worst_corner,
            "curr_worst_float":  curr_worst_float,
            "curr_worst_corner": curr_worst_corner,
        }

        if status_change == "regression":
            regressions.append(entry)
        elif status_change == "improvement":
            improvements.append(entry)
        else:
            value_changes.append(entry)

    value_changes.sort(key=compute_impact_score, reverse=True)

    return {
        "regressions":     regressions,
        "improvements":    improvements,
        "value_changes":   value_changes,
        "no_changes":      no_changes,
        "new_metrics":     new_metrics,
        "removed_metrics": removed_metrics,
    }


# =====================================================================
# Printing
# =====================================================================

def print_entry(entry, tag="", full_corners=False):
    """
    Print one changed metric entry.
    """
    if tag == "regression":
        label = "[REGRESSION]"
    elif tag == "improvement":
        label = "[IMPROVED]  "
    else:
        label = "            "

    spec_str = ""

    if entry["spec"]:
        spec_str = "  Spec: {0}".format(entry["spec"])

    status_str = "{0} -> {1}".format(
        status_label(entry["prev_pf"]),
        status_label(entry["curr_pf"])
    )

    nominal_str = ""

    if entry["prev_nominal"] != entry["curr_nominal"]:
        nominal_str = "  nominal: {0} -> {1}".format(
            entry["prev_nominal"],
            entry["curr_nominal"]
        )

    print("{0} {1}{2}".format(label, entry["output"], spec_str))
    print("           Status : {0}{1}".format(status_str, nominal_str))

    prev_worst = entry.get("prev_worst_corner")
    curr_worst = entry.get("curr_worst_corner")
    prev_float = entry.get("prev_worst_float")
    curr_float = entry.get("curr_worst_float")

    if prev_worst and curr_worst:
        pct_str = format_pct(prev_float, curr_float)
        same_corner = corner_label(prev_worst) == corner_label(curr_worst)

        if same_corner:
            print("           Worst  : {0}  {1} -> {2}  {3}".format(
                corner_label(prev_worst),
                prev_worst.get("value", ""),
                curr_worst.get("value", ""),
                pct_str
            ))
        else:
            print("           Worst before: {0} = {1}".format(
                corner_label(prev_worst),
                prev_worst.get("value", "")
            ))
            print("           Worst after : {0} = {1}  {2}".format(
                corner_label(curr_worst),
                curr_worst.get("value", ""),
                pct_str
            ))

    if full_corners and entry["changed_corners"]:
        print("           All changed corners:")

        for changed_corner in entry["changed_corners"]:
            delta_part = ""

            if changed_corner["delta_str"]:
                delta_part = "  Delta: {0}".format(changed_corner["delta_str"])

            print("             {0} {1}C:  {2} -> {3}{4}".format(
                changed_corner["process"],
                changed_corner["temperature"],
                changed_corner["prev_val"],
                changed_corner["curr_val"],
                delta_part
            ))

    print("")


def print_ranking_summary(all_changed):
    """
    Print ranked summary of changed metrics.
    """
    if not all_changed:
        return

    ranked = sorted(all_changed, key=compute_impact_score, reverse=True)

    print("Ranked by magnitude of change:")
    print("")

    for idx, entry in enumerate(ranked):
        if entry["status_change"] == "regression":
            tag = "[REGRESSION]"
        elif entry["status_change"] == "improvement":
            tag = "[IMPROVED]  "
        else:
            tag = "            "

        prev_float = entry.get("prev_worst_float")
        curr_float = entry.get("curr_worst_float")
        pct_str = format_pct(prev_float, curr_float)

        curr_worst = entry.get("curr_worst_corner")
        curr_label = corner_label(curr_worst) if curr_worst else ""

        status_note = ""

        if entry["status_change"] in ("regression", "improvement"):
            status_note = "  {0} -> {1}".format(
                status_label(entry["prev_pf"]),
                status_label(entry["curr_pf"])
            )

        print("  {0}. {1} {2:<30s}  worst {3:<10s}  {4}{5}".format(
            idx + 1,
            tag,
            entry["output"][:29],
            curr_label,
            pct_str,
            status_note
        ))

    print("")


def print_diff(diff, prev_path, curr_path, full_mode=False):
    """
    Print complete ADE XL result diff.
    """
    regressions = diff["regressions"]
    improvements = diff["improvements"]
    value_changes = diff["value_changes"]
    no_changes = diff["no_changes"]
    new_metrics = diff["new_metrics"]
    removed_metrics = diff["removed_metrics"]

    all_changed = regressions + improvements + value_changes

    print("")
    print("=" * 65)
    print("ADE XL Result Diff")
    print("Previous : {0}".format(os.path.basename(prev_path)))
    print("Current  : {0}".format(os.path.basename(curr_path)))
    print("Mode     : {0}".format(
        "full corners" if full_mode else "worst-corner"
    ))
    print("=" * 65)
    print("Regressions  : {0}".format(len(regressions)))
    print("Improvements : {0}".format(len(improvements)))
    print("Value changes: {0}".format(len(value_changes)))
    print("No changes   : {0}".format(len(no_changes)))

    if new_metrics:
        print("New metrics  : {0}".format(", ".join(new_metrics)))

    if removed_metrics:
        print("Removed      : {0}".format(", ".join(removed_metrics)))

    print("")

    if not all_changed and not new_metrics and not removed_metrics:
        print("No simulation result changes detected.")
        print("")
        return

    print_ranking_summary(all_changed)

    if regressions:
        print("--- REGRESSIONS " + "-" * 48)
        print("")

        for entry in regressions:
            print_entry(entry, "regression", full_mode)

    if improvements:
        print("--- IMPROVEMENTS " + "-" * 47)
        print("")

        for entry in improvements:
            print_entry(entry, "improvement", full_mode)

    if value_changes:
        print("--- VALUE CHANGES (sorted by magnitude) " + "-" * 24)
        print("")

        for entry in value_changes:
            print_entry(entry, "value", full_mode)

    if no_changes:
        print("--- NO CHANGES " + "-" * 49)
        print("    " + ", ".join(no_changes))
        print("")

    print("=" * 65)
    print("Summary: {0} regression(s), {1} improvement(s), {2} value change(s)".format(
        len(regressions),
        len(improvements),
        len(value_changes)
    ))
    print("=" * 65)
    print("")


# =====================================================================
# CLI Entry Point
# =====================================================================

def print_usage():
    """
    Print command-line usage.
    """
    print("Usage:")
    print("  python diff_adexl_results.py")
    print("      Auto-diff latest two adexl_results_*.json files")
    print("")
    print("  python diff_adexl_results.py --full")
    print("      Auto-diff latest two files and show all changed corners")
    print("")
    print("  python diff_adexl_results.py <prev_run> <curr_run> [--full]")
    print("      Diff adexl_results_NNN.json by run number")
    print("")
    print("  python diff_adexl_results.py <prev.json> <curr.json> [--full]")
    print("      Diff explicit JSON paths")
    print("")
    print("  python diff_adexl_results.py --results-dir <dir> [--full]")
    print("      Auto-diff latest two files in a specific results directory")
    print("")


def main():
    """
    Run command-line diff flow.
    """
    args = sys.argv[1:]

    try:
        prev_path, curr_path, full_mode = resolve_paths(args)
    except ValueError as error:
        print_usage()
        print("ERROR: {0}".format(error))
        sys.exit(1)

    try:
        prev_data = load_result_json(prev_path)
        curr_data = load_result_json(curr_path)
    except (IOError, ValueError) as error:
        print("ERROR: {0}".format(error))
        sys.exit(1)

    diff = diff_results(prev_data, curr_data)
    print_diff(diff, prev_path, curr_path, full_mode)


if __name__ == "__main__":
    main()
