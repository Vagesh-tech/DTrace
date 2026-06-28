#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DTrace
parse_adexl.py

Purpose
-------
Parse ADE XL Detail View CSV exports into structured JSON result files.

Responsibilities
----------------
- Locate the ADE XL scalar result table
- Classify output columns semantically
- Extract nominal, min, max, spec, and pass/fail fields
- Extract corner values
- Preserve process and temperature metadata
- Handle ADE XL column-shift cases
- Save parsed results as JSON

Notes
-----
- Python 2.6 compatible
- Designed for ADE XL Detail View CSV exports
- Can parse either:
    1. Explicit CSV file paths
    2. Interactive.N.csv files from an ADE XL documents directory
- Does not interact directly with Cadence APIs
"""

import csv
import json
import os
import sys
import re
import glob


# =====================================================================
# User configuration
# =====================================================================
#
# These defaults are used only for the legacy/manual Interactive.N.csv
# flow. The main DTrace callback flow passes an explicit CSV path.
#
# Example:
#   ADEXL_DOCS_DIR = "/path/to/cell/adexl/documents"
#   RESULTS_DIR    = "/path/to/design_tracker/adexl_results"
#
ADEXL_DOCS_DIR = "./adexl/documents"
RESULTS_DIR = "./design_tracker/adexl_results"


PASS_FAIL_VALUES = set([
    "pass",
    "fail",
    "near",
    "warning",
    "error",
])

ROLE_PATTERNS = [
    ("test",      ["test"]),
    ("output",    ["output"]),
    ("nominal",   ["nominal"]),
    ("spec",      ["spec", "limit"]),
    ("weight",    ["weight"]),
    ("pass_fail", ["pass/fail", "pass fail", "passfail", "status"]),
    ("min",       ["min"]),
    ("max",       ["max"]),
]


# =====================================================================
# Basic helpers
# =====================================================================

def is_pass_fail_string(value):
    """
    Return True if value looks like a pass/fail status field.
    """
    return (value or "").strip().lower() in PASS_FAIL_VALUES


def read_all_rows(csv_path):
    """
    Read all rows from an ADE XL CSV file.

    Python 2.6 csv module expects binary mode.
    """
    f = open(csv_path, "rb")
    try:
        reader = csv.reader(f)
        rows = [row for row in reader]
    finally:
        f.close()

    return rows


def first_label(row):
    """
    Return the first non-empty cell in a row, lower-cased.
    """
    for cell in row:
        value = (cell or "").strip().lower()
        if value:
            return value

    return ""


def find_header_row_idx(rows):
    """
    Find the ADE XL scalar result table header row.

    The parser identifies the table by locating the row whose first
    non-empty label is 'test'.
    """
    for idx, row in enumerate(rows):
        if first_label(row) == "test":
            return idx

    return None


def classify_roles(header):
    """
    Classify ADE XL result columns into semantic roles.

    Columns that are not classified as known roles are treated as
    corner columns.
    """
    role_to_col = {}

    for role, patterns in ROLE_PATTERNS:
        for col in header:
            col_lower = (col or "").strip().lower()

            for pattern in patterns:
                if re.search(r"\b" + re.escape(pattern) + r"\b", col_lower):
                    role_to_col[role] = col
                    break

            if role in role_to_col:
                break

    classified = set(role_to_col.values())
    corner_cols = [col for col in header if col not in classified]

    return role_to_col, corner_cols


def build_col_lookup(row_values, header):
    """
    Build a column-name to row-value lookup.
    """
    lookup = {}

    for idx, col in enumerate(header):
        if idx < len(row_values):
            lookup[col] = (row_values[idx] or "").strip()
        else:
            lookup[col] = ""

    return lookup


# =====================================================================
# Metadata extraction
# =====================================================================

def get_meta_lookup(meta_rows, corner_cols):
    """
    Extract process and temperature metadata for each corner column.

    ADE XL Detail View exports often place process and temperature
    information above the scalar result table. This function maps those
    metadata rows back to the actual corner columns.
    """
    temperature_by_corner = {}
    process_by_corner = {}

    meta_header = None

    for row in meta_rows:
        if first_label(row) == "parameter":
            meta_header = [(cell or "").strip() for cell in row]
            break

    if meta_header is None:
        return temperature_by_corner, process_by_corner

    corner_pos = {}

    for corner_col in corner_cols:
        if corner_col in meta_header:
            corner_pos[corner_col] = meta_header.index(corner_col)

    for row in meta_rows:
        if not row:
            continue

        label = first_label(row)

        if not label or label == "parameter":
            continue

        if "temperature" in label:
            for corner_col, idx in corner_pos.items():
                if idx < len(row):
                    temperature_by_corner[corner_col] = (row[idx] or "").strip()
        else:
            for corner_col, idx in corner_pos.items():
                if idx < len(row):
                    process_by_corner[corner_col] = (row[idx] or "").strip()

    return temperature_by_corner, process_by_corner


# =====================================================================
# Shift detection
# =====================================================================

def detect_shift(data_rows, role_to_col, header):
    """
    Detect ADE XL Weight-column shift cases.

    In some exports, an empty Weight field may be omitted, shifting
    subsequent fields left. If the Weight column contains pass/fail-like
    values in most populated rows, the parser treats the export as shifted.
    """
    weight_col = role_to_col.get("weight")

    if not weight_col:
        return False

    weight_idx = header.index(weight_col)

    pass_fail_count = 0
    total_count = 0

    for row in data_rows:
        if weight_idx < len(row):
            value = (row[weight_idx] or "").strip()

            if value:
                total_count += 1

                if is_pass_fail_string(value):
                    pass_fail_count += 1

    if total_count == 0:
        return False

    return float(pass_fail_count) / float(total_count) > 0.5


def apply_shift(row_values, header, role_to_col):
    """
    Correct a detected Weight-column shift by inserting an empty Weight field.
    """
    weight_col = role_to_col.get("weight")

    if weight_col:
        weight_idx = header.index(weight_col)
        row_values = list(row_values[:weight_idx]) + [""] + list(row_values[weight_idx:])

    return build_col_lookup(row_values, header)


# =====================================================================
# ADE XL parser
# =====================================================================

def parse_adexl(csv_path):
    """
    Parse one ADE XL Detail View CSV export.

    Parameters
    ----------
    csv_path : str
        Path to an ADE XL Detail View CSV export.

    Returns
    -------
    dict
        Structured ADE XL result data.
    """
    if not os.path.isfile(csv_path):
        raise IOError("CSV not found: {0}".format(csv_path))

    rows = read_all_rows(csv_path)

    if not rows:
        raise ValueError("CSV is empty: {0}".format(csv_path))

    header_idx = find_header_row_idx(rows)

    if header_idx is None:
        raise ValueError("Could not find Test header row in: {0}".format(csv_path))

    meta_rows = rows[:header_idx]
    header_row = rows[header_idx]
    data_rows_raw = rows[header_idx + 1:]

    header = [(cell or "").strip() for cell in header_row]

    role_to_col, corner_cols = classify_roles(header)
    temperature_by_corner, process_by_corner = get_meta_lookup(meta_rows, corner_cols)
    shift_active = detect_shift(data_rows_raw, role_to_col, header)

    results = []
    omitted = []

    for raw_row in data_rows_raw:
        if not raw_row or all((cell or "").strip() == "" for cell in raw_row):
            continue

        if shift_active:
            col_map = apply_shift(raw_row, header, role_to_col)
        else:
            col_map = build_col_lookup(raw_row, header)

        def get(role):
            col = role_to_col.get(role)
            if col:
                return col_map.get(col, "")
            return ""

        test_val = get("test")
        output_val = get("output")
        nominal_val = get("nominal")
        spec_val = get("spec")
        weight_val = get("weight")
        pass_fail_val = get("pass_fail")
        min_val = get("min")
        max_val = get("max")

        # Rows without scalar min/max values are usually waveform-like
        # outputs or non-scalar entries. DTrace omits them from scalar
        # comparison.
        if min_val == "" and max_val == "":
            omitted.append("{0} | {1}".format(test_val, output_val))
            continue

        corners = []

        for corner_col in corner_cols:
            value = col_map.get(corner_col, "")

            if value != "":
                corners.append({
                    "corner":      corner_col,
                    "process":     process_by_corner.get(corner_col, ""),
                    "temperature": temperature_by_corner.get(corner_col, ""),
                    "value":       value,
                })

        results.append({
            "test":      test_val,
            "output":    output_val,
            "nominal":   nominal_val,
            "spec":      spec_val,
            "weight":    weight_val,
            "pass_fail": pass_fail_val,
            "min":       min_val,
            "max":       max_val,
            "corners":   corners,
        })

    return {
        "source_file":              csv_path,
        "shift_correction_applied": shift_active,
        "columns":                  header,
        "corner_columns":           corner_cols,
        "omitted_rows":             omitted,
        "results":                  results,
    }


# =====================================================================
# Save helpers
# =====================================================================

def save_parsed_result(parsed, json_path):
    """
    Save parsed ADE XL data to JSON.
    """
    out_dir = os.path.dirname(json_path)

    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    out_f = open(json_path, "w")
    try:
        json.dump(parsed, out_f, indent=2)
    finally:
        out_f.close()


def parse_file_to_json(csv_path, json_path):
    """
    Parse an explicit CSV file and save to an explicit JSON path.
    """
    print("Parsing: {0}".format(csv_path))

    parsed = parse_adexl(csv_path)
    save_parsed_result(parsed, json_path)

    print("Saved  : {0}".format(json_path))
    print("Metrics: {0} parsed, {1} omitted".format(
        len(parsed["results"]),
        len(parsed["omitted_rows"])
    ))
    print("Corners: {0}".format(", ".join(parsed["corner_columns"])))
    print("")

    return json_path


# =====================================================================
# Legacy Interactive.N.csv support
# =====================================================================

def extract_run_number(csv_path):
    """
    Extract N from Interactive.N.csv.
    """
    basename = os.path.basename(csv_path)
    match = re.search(r"Interactive\.(\d+)\.csv", basename, re.IGNORECASE)

    if match:
        return int(match.group(1))

    return None


def find_latest_csv():
    """
    Find latest Interactive.N.csv in ADEXL_DOCS_DIR.
    """
    pattern = os.path.join(ADEXL_DOCS_DIR, "Interactive.*.csv")
    files = glob.glob(pattern)

    if not files:
        return None

    def sort_key(path):
        number = extract_run_number(path)
        if number is not None:
            return number
        return -1

    return sorted(files, key=sort_key)[-1]


def parse_and_save_interactive(run_number):
    """
    Parse Interactive.N.csv from ADEXL_DOCS_DIR and save result JSON.
    """
    csv_path = os.path.join(
        ADEXL_DOCS_DIR,
        "Interactive.{0}.csv".format(run_number)
    )

    json_path = os.path.join(
        RESULTS_DIR,
        "adexl_results_{0:03d}.json".format(run_number)
    )

    return parse_file_to_json(csv_path, json_path)


# =====================================================================
# CLI Entry Point
# =====================================================================

def print_usage():
    """
    Print command-line usage.
    """
    print("Usage:")
    print("  python parse_adexl.py")
    print("      Auto-detect latest Interactive.N.csv from ADEXL_DOCS_DIR")
    print("")
    print("  python parse_adexl.py <run_number> [<run_number> ...]")
    print("      Parse one or more Interactive.N.csv files")
    print("")
    print("  python parse_adexl.py --csv <input.csv> --out <output.json>")
    print("      Parse an explicit ADE XL CSV export")
    print("")


def main():
    """
    Dispatch command-line parser modes.
    """
    args = sys.argv[1:]

    try:
        if len(args) == 0:
            latest = find_latest_csv()

            if latest is None:
                print("ERROR: No Interactive.N.csv files found in: {0}".format(
                    ADEXL_DOCS_DIR
                ))
                sys.exit(1)

            run_number = extract_run_number(latest)

            print("Auto-detected latest: Interactive.{0}.csv".format(run_number))
            parse_and_save_interactive(run_number)
            return

        if len(args) == 4 and args[0] == "--csv" and args[2] == "--out":
            csv_path = args[1]
            json_path = args[3]
            parse_file_to_json(csv_path, json_path)
            return

        for arg in args:
            try:
                run_number = int(arg)
            except ValueError:
                print_usage()
                print("ERROR: expected integer run number, got '{0}'".format(arg))
                sys.exit(1)

            parse_and_save_interactive(run_number)

    except (IOError, ValueError) as error:
        print("ERROR: {0}".format(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
