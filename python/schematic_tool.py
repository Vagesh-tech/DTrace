#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DTrace
schematic_tool.py

Purpose
-------
Parse schematic checkpoints exported by Cadence SKILL into structured JSON
and compare successive schematic snapshots.

Responsibilities
----------------
- Parse schematic CSV exports
- Generate structured JSON schematic snapshots
- Compare schematic snapshots
- Report added, removed, and modified instances

Notes
-----
- Python 2.6 compatible
- Intended to be called by the SKILL schematic extractor and dtrace.py
- Does not interact directly with Cadence APIs
- The SKILL extractor runs inside Cadence Virtuoso separately
"""

import sys
import csv
import json
import os
from collections import OrderedDict


REQUIRED_CSV_COLUMNS = [
    "instance_name",
    "lib_name",
    "cell_name",
    "view_name",
    "param_name",
    "param_value",
]

REQUIRED_INSTANCE_KEYS = [
    "lib_name",
    "cell_name",
    "view_name",
    "params",
]

SUMMARY_PARAM_PRIORITY = [
    "model",
    "w",
    "l",
    "m",
    "fingers",
    "value",
    "r",
    "c",
    "vdc",
    "idc",
]


# =====================================================================
# CSV Parsing
# =====================================================================

def read_schematic_csv(csv_path):
    """
    Parse a schematic checkpoint CSV and group rows by instance_name.

    Empty-valued parameters are dropped, but valid zero values such as
    "0", "0.0", and "0m" are preserved.

    Parameters
    ----------
    csv_path : str
        Path to the schematic CSV exported by SKILL.

    Returns
    -------
    OrderedDict
        Instance-keyed schematic snapshot.
    """
    if not os.path.isfile(csv_path):
        raise IOError("CSV file not found: {0}".format(csv_path))

    instances = OrderedDict()
    conflicts = []

    f = open(csv_path, "rb")
    try:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("CSV file is empty - no header row found.")

        missing = [c for c in REQUIRED_CSV_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(
                "CSV is missing required column(s): {0}. Found columns: {1}".format(
                    ", ".join(missing),
                    ", ".join(reader.fieldnames)
                )
            )

        row_count = 0

        for row in reader:
            row_count += 1

            inst_name = (row["instance_name"] or "").strip()
            lib_name = (row["lib_name"] or "").strip()
            cell_name = (row["cell_name"] or "").strip()
            view_name = (row["view_name"] or "").strip()
            param_name = (row["param_name"] or "").strip()
            param_value = (row["param_value"] or "").strip()

            if not inst_name:
                print("  WARNING: row {0} has empty instance_name - skipped.".format(row_count))
                continue

            if inst_name not in instances:
                instances[inst_name] = {
                    "lib_name": lib_name,
                    "cell_name": cell_name,
                    "view_name": view_name,
                    "params": OrderedDict(),
                }
            else:
                existing = instances[inst_name]
                existing_meta = (
                    existing["lib_name"],
                    existing["cell_name"],
                    existing["view_name"],
                )
                current_meta = (
                    lib_name,
                    cell_name,
                    view_name,
                )

                if existing_meta != current_meta:
                    conflicts.append(
                        "{0}: row {1} has metadata ({2}/{3}/{4}) that conflicts with "
                        "earlier ({5}/{6}/{7}). Keeping the first one seen.".format(
                            inst_name,
                            row_count,
                            lib_name,
                            cell_name,
                            view_name,
                            existing["lib_name"],
                            existing["cell_name"],
                            existing["view_name"],
                        )
                    )

            if param_name in ("NO_CDF", "NO_PARAMS"):
                continue

            if param_value == "":
                continue

            instances[inst_name]["params"][param_name] = param_value

        if row_count == 0:
            print("  WARNING: CSV has a header but no data rows.")

    finally:
        f.close()

    if conflicts:
        print("")
        print("  WARNING: conflicting instance metadata detected:")
        for conflict in conflicts:
            print("    - {0}".format(conflict))

    return instances


def print_parse_summary(instances):
    """
    Print a compact schematic parse summary.
    """
    print("")
    print("Found {0} instances.".format(len(instances)))
    print("")

    for inst_name in instances:
        data = instances[inst_name]
        cell_name = data["cell_name"]
        params = data["params"]

        headline_bits = []

        for key in SUMMARY_PARAM_PRIORITY:
            if key in params:
                headline_bits.append("{0}={1}".format(key, params[key]))

        if headline_bits:
            headline = " | ".join(headline_bits)
        else:
            headline = "(no key params)"

        print("{0:<6s} | {1:<8s} | {2}".format(
            inst_name,
            cell_name,
            headline
        ))


def run_parse(csv_path):
    """
    Parse one schematic CSV and save a JSON snapshot next to it.
    """
    instances = read_schematic_csv(csv_path)
    print_parse_summary(instances)

    json_path = os.path.splitext(csv_path)[0] + ".json"

    out_f = open(json_path, "w")
    try:
        json.dump(instances, out_f, indent=2)
    finally:
        out_f.close()

    print("")
    print("Saved parsed snapshot to {0}".format(json_path))


# =====================================================================
# Snapshot Comparison
# =====================================================================

def load_snapshot(path):
    """
    Load a schematic JSON snapshot.
    """
    if not os.path.isfile(path):
        raise IOError("Snapshot file not found: {0}".format(path))

    f = open(path, "r")
    try:
        raw = f.read()
    finally:
        f.close()

    if not raw.strip():
        raise ValueError("Snapshot file is empty: {0}".format(path))

    try:
        data = json.loads(raw)
    except ValueError as error:
        raise ValueError("Invalid JSON in {0}: {1}".format(path, error))

    if not isinstance(data, dict):
        raise ValueError(
            "Snapshot JSON in {0} must be an object keyed by instance name.".format(path)
        )

    return data


def instance_missing_keys(entry):
    """
    Return required keys missing from a schematic instance entry.
    """
    if not isinstance(entry, dict):
        return REQUIRED_INSTANCE_KEYS[:]

    return [key for key in REQUIRED_INSTANCE_KEYS if key not in entry]


def format_instance_header(name, entry):
    """
    Format one instance header for human-readable diff output.
    """
    lib_name = entry.get("lib_name", "?")
    cell_name = entry.get("cell_name", "?")
    view_name = entry.get("view_name", "?")

    return "{0} | {1}/{2}/{3}".format(
        name,
        lib_name,
        cell_name,
        view_name
    )


def diff_instance(prev_entry, curr_entry):
    """
    Compare two schematic instance entries.

    Returns
    -------
    list
        Human-readable change strings.
    """
    changes = []

    for field in ("lib_name", "cell_name", "view_name"):
        prev_value = prev_entry.get(field)
        curr_value = curr_entry.get(field)

        if prev_value != curr_value:
            changes.append("{0}: {1} -> {2}".format(
                field,
                prev_value,
                curr_value
            ))

    prev_params = prev_entry.get("params") or {}
    curr_params = curr_entry.get("params") or {}

    all_param_keys = sorted(
        set(list(prev_params.keys()) + list(curr_params.keys()))
    )

    for key in all_param_keys:
        in_prev = key in prev_params
        in_curr = key in curr_params
        prev_value = prev_params.get(key)
        curr_value = curr_params.get(key)

        if not in_prev and in_curr:
            changes.append("params.{0}: (added) -> {1}".format(
                key,
                curr_value
            ))
        elif in_prev and not in_curr:
            changes.append("params.{0}: {1} -> (removed)".format(
                key,
                prev_value
            ))
        elif prev_value != curr_value:
            changes.append("params.{0}: {1} -> {2}".format(
                key,
                prev_value,
                curr_value
            ))

    return changes


def run_diff(prev_path, curr_path):
    """
    Compare two schematic JSON snapshots and print a human-readable diff.
    """
    prev = load_snapshot(prev_path)
    curr = load_snapshot(curr_path)

    prev_names = set(prev.keys())
    curr_names = set(curr.keys())

    added_names = sorted(curr_names - prev_names)
    removed_names = sorted(prev_names - curr_names)
    common_names = sorted(prev_names & curr_names)

    modified = []
    skipped_malformed = []

    for name in common_names:
        prev_entry = prev[name]
        curr_entry = curr[name]

        missing_prev = instance_missing_keys(prev_entry)
        missing_curr = instance_missing_keys(curr_entry)

        if missing_prev or missing_curr:
            skipped_malformed.append(
                "{0}: malformed entry (missing keys - prev: {1}, curr: {2}). Skipped.".format(
                    name,
                    missing_prev or "none",
                    missing_curr or "none"
                )
            )
            continue

        changes = diff_instance(prev_entry, curr_entry)

        if changes:
            modified.append((name, curr_entry, changes))

    print("Schematic Snapshot Diff")
    print("")

    if skipped_malformed:
        print("WARNING: some instances had malformed entries and were skipped:")
        for line in skipped_malformed:
            print("  - {0}".format(line))
        print("")

    has_changes = bool(added_names) or bool(removed_names) or bool(modified)

    if not has_changes:
        print("No schematic changes detected.")
        return

    if added_names:
        print("Added Instances")
        for name in added_names:
            print(format_instance_header(name, curr[name]))
        print("")

    if removed_names:
        print("Removed Instances")
        for name in removed_names:
            print(format_instance_header(name, prev[name]))
        print("")

    if modified:
        print("Modified Instances")
        for name, entry, changes in modified:
            print(format_instance_header(name, entry))
            for line in changes:
                print("    {0}".format(line))
        print("")


# =====================================================================
# CLI Entry Point
# =====================================================================

def print_usage():
    """
    Print command-line usage.
    """
    print("Usage:")
    print("  python schematic_tool.py parse <schematic_csv_path>")
    print("  python schematic_tool.py diff <previous_snapshot.json> <current_snapshot.json>")
    print("")
    print("Shorthand:")
    print("  python schematic_tool.py <schematic.csv>")
    print("  python schematic_tool.py <previous.json> <current.json>")


def main():
    """
    Dispatch CLI commands.
    """
    args = sys.argv[1:]

    try:
        if len(args) == 2 and args[0] in ("parse", "diff"):
            mode, path1 = args

            if mode == "parse":
                run_parse(path1)
            else:
                print_usage()
                sys.exit(1)

            return

        if len(args) == 3 and args[0] in ("parse", "diff"):
            mode, path1, path2 = args

            if mode == "diff":
                run_diff(path1, path2)
            else:
                print_usage()
                sys.exit(1)

            return

        if len(args) == 1 and args[0].lower().endswith(".csv"):
            run_parse(args[0])
            return

        if (
            len(args) == 2 and
            args[0].lower().endswith(".json") and
            args[1].lower().endswith(".json")
        ):
            run_diff(args[0], args[1])
            return

        print_usage()
        sys.exit(1)

    except (IOError, ValueError) as error:
        print("ERROR: {0}".format(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
