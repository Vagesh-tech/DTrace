#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DTrace
dtrace.py

Purpose
-------
Main checkpoint orchestration engine for DTrace.

Responsibilities
----------------
- Manage pending schematic checkpoints
- Complete checkpoints using exported ADE XL CSV results
- Compare schematic snapshots
- Compare ADE XL setup variables
- Compare parsed ADE XL simulation results
- Prompt for designer notes
- Generate immutable checkpoint reports
- Maintain project history index

Notes
-----
- Python 2.6 compatible
- Designed to be called from Cadence SKILL and from terminal
- Supports both:
    1. ADE XL callback flow using explicit exported CSV
    2. Legacy/manual Interactive.N.csv flow
"""

import sys
import os
import json
import re
import glob
import datetime
import time
import traceback

from schematic_tool import (
    load_snapshot,
    instance_missing_keys,
    diff_instance,
)

from diff_adexl_results import (
    load_result_json,
    diff_results,
    format_pct,
    corner_label,
    status_label,
)

import parse_adexl as _pa


# =====================================================================
# User configuration
# =====================================================================

DESIGN_TRACKER_DIR = os.environ.get(
    "DTRACE_BASE_DIR",
    "./design_tracker"
)

CHECKPOINTS_DIR = os.path.join(DESIGN_TRACKER_DIR, "checkpoints")
ADEXL_RESULTS_DIR = os.path.join(DESIGN_TRACKER_DIR, "adexl_results")
REPORTS_DIR = os.path.join(DESIGN_TRACKER_DIR, "reports")

INDEX_PATH = os.path.join(DESIGN_TRACKER_DIR, "index.json")
STATE_PATH = os.path.join(DESIGN_TRACKER_DIR, "dtrace_state.json")
LOG_PATH = os.path.join(DESIGN_TRACKER_DIR, "dtrace.log")
PID_PATH = os.path.join(DESIGN_TRACKER_DIR, "watcher.pid")

ADEXL_DOCS_DIR = os.environ.get(
    "DTRACE_ADEXL_DOCS_DIR",
    _pa.ADEXL_DOCS_DIR
)

NOTE_MIN_LENGTH = 3
MAX_VALUE_CHANGES_SHOWN = 10
MAX_HISTORY_SHOWN = 5
MAX_SCHEMATIC_ITEMS = 5
MAX_INSTANCE_CHANGES = 3
MAX_RESULT_SUMMARY = 5
POLL_INTERVAL_SEC = 2
FILE_STABLE_SEC = 4


# =====================================================================
# Basic utilities
# =====================================================================

def ensure_dirs():
    for directory in (
        DESIGN_TRACKER_DIR,
        CHECKPOINTS_DIR,
        ADEXL_RESULTS_DIR,
        REPORTS_DIR,
    ):
        if not os.path.isdir(directory):
            os.makedirs(directory)


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    ensure_dirs()

    line = "[{0}] {1}\n".format(now_str(), msg)

    try:
        log_file = open(LOG_PATH, "a")
        try:
            log_file.write(line)
        finally:
            log_file.close()
    except Exception:
        pass


def read_json(path, default_value):
    if not os.path.isfile(path):
        return default_value

    json_file = open(path, "r")
    try:
        raw = json_file.read()
    finally:
        json_file.close()

    if not raw.strip():
        return default_value

    return json.loads(raw)


def write_json(path, data):
    ensure_dirs()

    json_file = open(path, "w")
    try:
        json.dump(data, json_file, indent=2)
    finally:
        json_file.close()


def load_index():
    try:
        data = read_json(INDEX_PATH, {"checkpoints": []})
    except ValueError as error:
        raise ValueError("Malformed index.json: {0}".format(error))

    if not isinstance(data, dict) or "checkpoints" not in data:
        raise ValueError("index.json missing checkpoints list")

    if not isinstance(data["checkpoints"], list):
        raise ValueError("index.json checkpoints must be a list")

    return data


def save_index(index):
    write_json(INDEX_PATH, index)


def load_state():
    try:
        return read_json(STATE_PATH, {})
    except ValueError:
        return {}


def save_state(state):
    write_json(STATE_PATH, state)


# =====================================================================
# Schematic checkpoint discovery
# =====================================================================

def _checkpoint_num_from_path(path):
    match = re.search(r"checkpoint_(\d+)\.json$", os.path.basename(path))

    if match:
        return int(match.group(1))

    return None


def find_latest_schematic_checkpoint(used_nums):
    files = glob.glob(os.path.join(CHECKPOINTS_DIR, "checkpoint_*.json"))
    candidates = []

    for path in files:
        number = _checkpoint_num_from_path(path)

        if number is not None and number not in used_nums:
            candidates.append((number, path))

    if not candidates:
        if not files:
            raise IOError("No schematic checkpoints found in {0}".format(
                CHECKPOINTS_DIR
            ))

        raise IOError(
            "No new schematic checkpoint found. "
            "All checkpoint JSON files are already used in index/state."
        )

    candidates.sort(key=lambda item: item[0])

    return candidates[-1]


# =====================================================================
# ADE XL CSV discovery for legacy/manual flow
# =====================================================================

def extract_interactive_run_number(csv_path):
    match = re.search(
        r"Interactive\.(\d+)\.csv$",
        os.path.basename(csv_path),
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def find_latest_adexl_csv():
    pattern = os.path.join(ADEXL_DOCS_DIR, "Interactive.*.csv")
    files = glob.glob(pattern)

    if not files:
        return None

    def key(path):
        number = extract_interactive_run_number(path)
        if number is not None:
            return number
        return -1

    return sorted(files, key=key)[-1]


def is_file_stable(path):
    if not os.path.isfile(path):
        return False

    return (time.time() - os.path.getmtime(path)) >= FILE_STABLE_SEC


# =====================================================================
# Result numbering and explicit CSV parsing
# =====================================================================

def next_result_id(index):
    max_id = 0

    for entry in index.get("checkpoints", []):
        value = entry.get("adexl_run")

        if isinstance(value, int) and value > max_id:
            max_id = value
        else:
            try:
                if value is not None and int(value) > max_id:
                    max_id = int(value)
            except Exception:
                pass

    return max_id + 1


def copy_file(src, dst):
    src_file = open(src, "rb")
    try:
        data = src_file.read()
    finally:
        src_file.close()

    dst_file = open(dst, "wb")
    try:
        dst_file.write(data)
    finally:
        dst_file.close()


def parse_explicit_csv_to_json(csv_path, result_id):
    """
    Copy explicit ADE XL CSV into DTrace storage, parse it, and return
    stable CSV / JSON paths.
    """
    ensure_dirs()

    if not os.path.isfile(csv_path):
        raise IOError("CSV not found: {0}".format(csv_path))

    stable_csv = os.path.join(
        ADEXL_RESULTS_DIR,
        "dtrace_results_{0:04d}.csv".format(result_id)
    )

    copy_file(csv_path, stable_csv)

    parsed = _pa.parse_adexl(stable_csv)

    json_path = os.path.join(
        ADEXL_RESULTS_DIR,
        "adexl_results_{0:03d}.json".format(result_id)
    )

    write_json(json_path, parsed)

    return stable_csv, json_path


# =====================================================================
# Diff wrappers
# =====================================================================

def run_schematic_diff(prev_sch_num, curr_sch_num):
    prev_path = os.path.join(
        CHECKPOINTS_DIR,
        "checkpoint_{0:04d}.json".format(prev_sch_num)
    )
    curr_path = os.path.join(
        CHECKPOINTS_DIR,
        "checkpoint_{0:04d}.json".format(curr_sch_num)
    )

    prev = load_snapshot(prev_path)
    curr = load_snapshot(curr_path)

    prev_names = set(prev.keys())
    curr_names = set(curr.keys())

    added = sorted(curr_names - prev_names)
    removed = sorted(prev_names - curr_names)
    modified = []
    skipped = []

    for name in sorted(prev_names & curr_names):
        prev_entry = prev[name]
        curr_entry = curr[name]

        if instance_missing_keys(prev_entry) or instance_missing_keys(curr_entry):
            skipped.append(name)
            continue

        changes = diff_instance(prev_entry, curr_entry)

        if changes:
            modified.append({
                "instance": name,
                "lib_name": curr_entry.get("lib_name", ""),
                "cell_name": curr_entry.get("cell_name", ""),
                "view_name": curr_entry.get("view_name", ""),
                "changes": changes,
            })

    return {
        "prev_checkpoint": prev_sch_num,
        "curr_checkpoint": curr_sch_num,
        "prev_file": os.path.basename(prev_path),
        "curr_file": os.path.basename(curr_path),
        "added": added,
        "removed": removed,
        "modified": modified,
        "skipped": skipped,
    }


def run_adexl_diff(prev_result_id, curr_result_id):
    prev_path = os.path.join(
        ADEXL_RESULTS_DIR,
        "adexl_results_{0:03d}.json".format(prev_result_id)
    )
    curr_path = os.path.join(
        ADEXL_RESULTS_DIR,
        "adexl_results_{0:03d}.json".format(curr_result_id)
    )

    prev_data = load_result_json(prev_path)
    curr_data = load_result_json(curr_path)

    diff = diff_results(prev_data, curr_data)
    diff["prev_adexl"] = prev_result_id
    diff["curr_adexl"] = curr_result_id

    return diff


def adexl_setup_path_from_schematic_num(num):
    return os.path.join(
        CHECKPOINTS_DIR,
        "checkpoint_{0:04d}_adexl_setup.json".format(num)
    )


def load_adexl_setup_by_schematic_num(num):
    path = adexl_setup_path_from_schematic_num(num)

    default_data = {
        "checkpoint_id": "checkpoint_{0:04d}".format(num),
        "type": "adexl_setup",
        "variables": {},
    }

    if not os.path.isfile(path):
        return default_data

    return read_json(path, default_data)


def diff_adexl_setup(old_setup, new_setup):
    old_vars = old_setup.get("variables", {}) if old_setup else {}
    new_vars = new_setup.get("variables", {}) if new_setup else {}

    added = {}
    removed = {}
    changed = {}

    for key in sorted(new_vars.keys()):
        new_value = new_vars[key]

        if key not in old_vars:
            added[key] = new_value
        elif str(old_vars[key]) != str(new_value):
            changed[key] = {
                "old": old_vars[key],
                "new": new_value,
            }

    for key in sorted(old_vars.keys()):
        if key not in new_vars:
            removed[key] = old_vars[key]

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def format_adexl_value(value):
    value_str = str(value).strip()

    try:
        numeric_value = float(value_str)
    except Exception:
        return value_str

    if numeric_value != 0 and abs(numeric_value) < 1.0:
        milli_value = numeric_value * 1000.0

        if abs(milli_value - round(milli_value)) < 1e-9:
            return "{0:g}m".format(milli_value)

    return value_str


def format_adexl_setup_diff(setup_diff):
    lines = []

    lines.append("")
    lines.append("ADE XL SETUP CHANGES:")

    if (
        not setup_diff.get("added") and
        not setup_diff.get("removed") and
        not setup_diff.get("changed")
    ):
        lines.append("  No ADE XL setup changes detected.")
        return "\n".join(lines)

    for key in sorted(setup_diff.get("added", {}).keys()):
        lines.append("  {0}:".format(key))
        lines.append("      added = {0}".format(
            format_adexl_value(setup_diff["added"][key])
        ))

    for key in sorted(setup_diff.get("removed", {}).keys()):
        lines.append("  {0}:".format(key))
        lines.append("      removed previous value = {0}".format(
            format_adexl_value(setup_diff["removed"][key])
        ))

    for key in sorted(setup_diff.get("changed", {}).keys()):
        change = setup_diff["changed"][key]
        lines.append("  {0}:".format(key))
        lines.append("      {0} -> {1}".format(
            format_adexl_value(change["old"]),
            format_adexl_value(change["new"])
        ))

    return "\n".join(lines)


# =====================================================================
# Summary generation
# =====================================================================

def summarize_schematic_diff(diff):
    lines = []

    if not diff:
        return ["No schematic data."]

    if (
        not diff.get("added") and
        not diff.get("removed") and
        not diff.get("modified")
    ):
        return ["No schematic changes."]

    if diff.get("added"):
        lines.append("Added: {0}".format(", ".join(diff["added"])))

    if diff.get("removed"):
        lines.append("Removed: {0}".format(", ".join(diff["removed"])))

    for item in diff.get("modified", [])[:MAX_SCHEMATIC_ITEMS]:
        instance = item.get("instance", "?")
        cell = item.get("cell_name", "?")

        lines.append("{0} | {1}:".format(instance, cell))

        for change in item.get("changes", [])[:MAX_INSTANCE_CHANGES]:
            lines.append("  {0}".format(change))

    return lines


def summarize_adexl_setup_diff(diff):
    lines = []

    if not diff:
        return ["No ADE XL setup data."]

    if (
        not diff.get("added") and
        not diff.get("removed") and
        not diff.get("changed")
    ):
        return ["No ADE XL setup changes."]

    for key in sorted(diff.get("added", {}).keys()):
        lines.append("{0}: added = {1}".format(
            key,
            format_adexl_value(diff["added"][key])
        ))

    for key in sorted(diff.get("removed", {}).keys()):
        lines.append("{0}: removed previous value = {1}".format(
            key,
            format_adexl_value(diff["removed"][key])
        ))

    for key in sorted(diff.get("changed", {}).keys()):
        change = diff["changed"][key]

        lines.append("{0}: {1} -> {2}".format(
            key,
            format_adexl_value(change["old"]),
            format_adexl_value(change["new"])
        ))

    return lines


def summarize_adexl_result_diff(diff, max_items=MAX_RESULT_SUMMARY):
    lines = []

    if not diff:
        return ["No result data."]

    items = []
    items.extend(diff.get("regressions", []))
    items.extend(diff.get("improvements", []))
    items.extend(diff.get("value_changes", []))

    if not items:
        return ["No major result changes."]

    def one_line(entry):
        prev_worst = entry.get("prev_worst_corner")
        curr_worst = entry.get("curr_worst_corner")

        if prev_worst and curr_worst:
            return "{0}: {1} -> {2}".format(
                entry.get("output", "?"),
                prev_worst.get("value", "?"),
                curr_worst.get("value", "?")
            )

        return "{0}".format(entry.get("output", "?"))

    for entry in items[:max_items]:
        lines.append(one_line(entry))

    if len(items) > max_items:
        lines.append("... and {0} more result changes".format(
            len(items) - max_items
        ))

    return lines


def _history_sort_key(item):
    entry, report = item

    try:
        return int(entry.get("id", 0))
    except Exception:
        return 0


def build_recent_history_text(checkpoints, max_history=MAX_HISTORY_SHOWN):
    entries = []

    for entry in checkpoints:
        if entry.get("type") != "comparison":
            continue

        if not entry.get("report"):
            continue

        report_path = os.path.join(
            REPORTS_DIR,
            os.path.basename(entry.get("report"))
        )

        if not os.path.isfile(report_path):
            continue

        try:
            report = read_json(report_path, {})
        except Exception:
            continue

        entries.append((entry, report))

    if not entries:
        return "RECENT DESIGN HISTORY\n\nNo previous comparison checkpoints yet."

    entries.sort(key=_history_sort_key)

    total_entries = len(entries)
    entries = entries[-max_history:]

    lines = []
    lines.append("RECENT DESIGN HISTORY (Latest {0} of {1} Completed Comparisons)".format(
        len(entries),
        total_entries
    ))
    lines.append("=" * 70)

    for idx, item in enumerate(entries):
        entry, report = item

        checkpoint = report.get("checkpoint") or "{0:04d}".format(
            entry.get("id", 0)
        )
        timestamp = report.get("created_at") or entry.get("timestamp") or "?"
        note = (report.get("note") or entry.get("note") or "(No note)").strip()

        lines.append("")
        lines.append("Checkpoint {0}".format(checkpoint))
        lines.append("-" * 70)
        lines.append("Time: {0}".format(timestamp))
        lines.append("")
        lines.append("Note:")
        lines.append(note)
        lines.append("")

        lines.append("Schematic:")
        for summary in summarize_schematic_diff(report.get("schematic_diff")):
            lines.append("  {0}".format(summary))
        lines.append("")

        lines.append("ADE XL Setup:")
        for summary in summarize_adexl_setup_diff(report.get("adexl_setup_diff")):
            lines.append("  {0}".format(summary))
        lines.append("")

        lines.append("Performance:")
        for summary in summarize_adexl_result_diff(report.get("adexl_diff")):
            lines.append("  {0}".format(summary))

        if idx != len(entries) - 1:
            lines.append("")
            lines.append("=" * 70)

    lines.append("")
    lines.append("=" * 70)
    lines.append("END OF HISTORY")
    lines.append("=" * 70)

    return "\n".join(lines)


# =====================================================================
# Text generation
# =====================================================================

def build_diff_text(sch_diff, setup_diff, adexl_diff):
    lines = []

    lines.append("=" * 70)
    lines.append("CURRENT ITERATION")
    lines.append("=" * 70)
    lines.append("")

    lines.append("SCHEMATIC CHANGES (checkpoint_{0:04d} -> checkpoint_{1:04d}):".format(
        sch_diff["prev_checkpoint"],
        sch_diff["curr_checkpoint"]
    ))

    if (
        not sch_diff.get("added") and
        not sch_diff.get("removed") and
        not sch_diff.get("modified")
    ):
        lines.append("  No schematic changes.")
    else:
        if sch_diff.get("added"):
            lines.append("  Added: {0}".format(", ".join(sch_diff["added"])))

        if sch_diff.get("removed"):
            lines.append("  Removed: {0}".format(", ".join(sch_diff["removed"])))

        for item in sch_diff.get("modified", []):
            lines.append("  {0} | {1}:".format(
                item.get("instance"),
                item.get("cell_name")
            ))

            for change in item.get("changes", []):
                lines.append("      {0}".format(change))

    lines.append(format_adexl_setup_diff(setup_diff))

    lines.append("")
    lines.append("PERFORMANCE CHANGES (result {0} -> result {1}):".format(
        adexl_diff.get("prev_adexl", "?"),
        adexl_diff.get("curr_adexl", "?")
    ))

    regressions = adexl_diff.get("regressions", [])
    improvements = adexl_diff.get("improvements", [])
    value_changes = adexl_diff.get("value_changes", [])
    no_changes = adexl_diff.get("no_changes", [])
    new_metrics = adexl_diff.get("new_metrics", [])
    removed_metrics = adexl_diff.get("removed_metrics", [])

    lines.append("  Regressions: {0}   Improvements: {1}   Value changes: {2}".format(
        len(regressions),
        len(improvements),
        len(value_changes)
    ))

    if new_metrics:
        lines.append("  New metrics: {0}".format(", ".join(new_metrics)))

    if removed_metrics:
        lines.append("  Removed metrics: {0}".format(", ".join(removed_metrics)))

    def add_entry(entry, tag):
        prev_worst = entry.get("prev_worst_corner")
        curr_worst = entry.get("curr_worst_corner")
        pct = format_pct(
            entry.get("prev_worst_float"),
            entry.get("curr_worst_float")
        )

        lines.append("  {0} {1}  [{2} -> {3}]".format(
            tag,
            entry.get("output", "?"),
            status_label(entry.get("prev_pf", "")),
            status_label(entry.get("curr_pf", ""))
        ))

        if prev_worst and curr_worst:
            lines.append("      Worst: {0}  {1} -> {2}  {3}".format(
                corner_label(curr_worst),
                prev_worst.get("value", "?"),
                curr_worst.get("value", "?"),
                pct
            ))

    for entry in regressions:
        add_entry(entry, "[REGRESSION]")

    for entry in improvements:
        add_entry(entry, "[IMPROVED]  ")

    for entry in value_changes[:MAX_VALUE_CHANGES_SHOWN]:
        add_entry(entry, "           ")

    if len(value_changes) > MAX_VALUE_CHANGES_SHOWN:
        lines.append("  ... and {0} more value changes".format(
            len(value_changes) - MAX_VALUE_CHANGES_SHOWN
        ))

    if no_changes:
        lines.append("  No changes: {0}".format(", ".join(no_changes[:6])))

    return "\n".join(lines)


# =====================================================================
# User note UI
# =====================================================================

def prompt_note_terminal():
    print("Enter designer note (minimum {0} characters):".format(NOTE_MIN_LENGTH))

    while True:
        try:
            try:
                note = raw_input("> ").strip()
            except NameError:
                note = input("> ").strip()

            if len(note) >= NOTE_MIN_LENGTH:
                return note

            print("Error: note must contain at least {0} non-space characters.".format(
                NOTE_MIN_LENGTH
            ))

        except KeyboardInterrupt:
            print("")
            print("Note interrupted. Saving checkpoint with placeholder note.")
            return "[NO NOTE PROVIDED - USER INTERRUPTED INPUT]"


def _import_tkinter():
    try:
        import Tkinter as tk
        import tkMessageBox as tkmsg
        return tk, tkmsg
    except ImportError:
        pass

    import tkinter as tk
    import tkinter.messagebox as tkmsg

    return tk, tkmsg


def show_baseline_notification(checkpoint_num_str, sch_num, result_id):
    msg = (
        "Checkpoint {0} stored as RESULT BASELINE.\n\n"
        "Schematic: checkpoint_{1:04d}\n"
        "Result   : {2}\n\n"
        "No comparison yet. Make a change and run DTrace again."
    ).format(
        checkpoint_num_str,
        sch_num,
        result_id
    )

    try:
        tk, tkmsg = _import_tkinter()
        root = tk.Tk()
        root.withdraw()
        tkmsg.showinfo("DTrace Baseline", msg)
        root.destroy()
    except Exception:
        log(msg)
        print(msg)


def show_note_popup(diff_text, history_text, checkpoint_num_str):
    try:
        tk, tkmsg = _import_tkinter()
    except Exception:
        print(history_text)
        print("")
        print(diff_text)
        print("")
        return prompt_note_terminal()

    result = [None]

    root = tk.Tk()
    root.title("DTrace Checkpoint {0}".format(checkpoint_num_str))
    root.geometry("760x600")

    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    tk.Label(
        root,
        text="Recent Design History:",
        font=("TkDefaultFont", 10, "bold")
    ).pack(anchor="w", padx=10, pady=(8, 2))

    notes = tk.Text(
        root,
        height=15,
        bg="#f0f0f0",
        font=("Courier", 9),
        wrap="word"
    )
    notes.insert("1.0", history_text)
    notes.config(state="disabled")
    notes.pack(fill="x", padx=10)

    tk.Label(
        root,
        text="Current Changes:",
        font=("TkDefaultFont", 10, "bold")
    ).pack(anchor="w", padx=10, pady=(8, 2))

    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10)

    scroll = tk.Scrollbar(frame)
    scroll.pack(side="right", fill="y")

    text = tk.Text(
        frame,
        bg="#f0f0f0",
        font=("Courier", 9),
        wrap="none",
        yscrollcommand=scroll.set
    )
    text.insert("1.0", diff_text)
    text.config(state="disabled")
    text.pack(side="left", fill="both", expand=True)

    scroll.config(command=text.yview)

    tk.Label(
        root,
        text="Designer Note (required, min {0} chars):".format(
            NOTE_MIN_LENGTH
        ),
        font=("TkDefaultFont", 10, "bold")
    ).pack(anchor="w", padx=10, pady=(8, 2))

    note_var = tk.StringVar()

    entry = tk.Entry(
        root,
        textvariable=note_var,
        font=("TkDefaultFont", 11)
    )
    entry.pack(fill="x", padx=10, pady=(0, 8))
    entry.focus_set()

    buttons = tk.Frame(root)
    buttons.pack(fill="x", padx=10, pady=(0, 8))

    def save():
        note = note_var.get().strip()

        if len(note) < NOTE_MIN_LENGTH:
            tkmsg.showerror(
                "Note Required",
                "Note must contain at least {0} characters.".format(
                    NOTE_MIN_LENGTH
                )
            )
            entry.focus_set()
            return

        result[0] = note
        root.destroy()

    def cancel():
        if tkmsg.askyesno(
            "Skip Note",
            "Save this checkpoint without a note?"
        ):
            result[0] = "[NO NOTE PROVIDED]"
            root.destroy()

    tk.Button(
        buttons,
        text="Save Checkpoint",
        command=save
    ).pack(side="left")

    tk.Button(
        buttons,
        text="Cancel",
        command=cancel
    ).pack(side="right")

    entry.bind("<Return>", lambda event: save())

    root.mainloop()

    return result[0]


def show_success_popup(checkpoint_num_str, note):
    msg = "Checkpoint {0} saved.\n\nNote: {1}".format(
        checkpoint_num_str,
        note
    )

    try:
        tk, tkmsg = _import_tkinter()
        root = tk.Tk()
        root.withdraw()
        tkmsg.showinfo("DTrace Saved", msg)
        root.destroy()
    except Exception:
        log(msg)
        print(msg)


# =====================================================================
# Checkpoint completion
# =====================================================================

def complete_checkpoint(pending, csv_path, result_id, result_json_path, use_gui=True):
    ensure_dirs()

    log("Completing checkpoint: schematic={0}, result_id={1}, csv={2}".format(
        pending.get("schematic_checkpoint_num"),
        result_id,
        os.path.basename(csv_path)
    ))

    index = load_index()
    checkpoints = index["checkpoints"]

    curr_sch_num = pending.get("schematic_checkpoint_num")
    curr_sch_path = os.path.join(
        CHECKPOINTS_DIR,
        "checkpoint_{0:04d}.json".format(curr_sch_num)
    )

    if not os.path.isfile(curr_sch_path):
        raise IOError("Schematic checkpoint file not found: {0}".format(
            curr_sch_path
        ))

    for entry in checkpoints:
        if (
            entry.get("type") in ("result_baseline", "comparison") and
            entry.get("schematic_checkpoint") == curr_sch_num
        ):
            raise RuntimeError(
                "Schematic checkpoint_{0:04d} is already attached to a result.".format(
                    curr_sch_num
                )
            )

    result_entries = [
        entry for entry in checkpoints
        if (
            entry.get("type") in ("result_baseline", "comparison") and
            entry.get("adexl_run") is not None
        )
    ]

    is_baseline = (len(result_entries) == 0)

    new_id = len(checkpoints)
    num_str = "{0:04d}".format(new_id)
    created_at = now_str()

    report_filename = "checkpoint_{0}_report.json".format(num_str)
    report_path = os.path.join(REPORTS_DIR, report_filename)

    if is_baseline:
        entry = {
            "id": new_id,
            "type": "result_baseline",
            "tracker_checkpoint": num_str,
            "schematic_checkpoint": curr_sch_num,
            "schematic_file": os.path.basename(curr_sch_path),
            "adexl_run": result_id,
            "adexl_csv": os.path.basename(csv_path),
            "adexl_result_json": os.path.basename(result_json_path),
            "report": None,
            "timestamp": created_at,
            "note": None,
        }

        checkpoints.append(entry)
        save_index(index)

        log("Checkpoint {0} stored as RESULT BASELINE.".format(num_str))
        print("Checkpoint {0} stored as RESULT BASELINE.".format(num_str))

        if use_gui:
            show_baseline_notification(num_str, curr_sch_num, result_id)

        return

    prev = result_entries[-1]
    prev_sch_num = prev["schematic_checkpoint"]
    prev_result_id = prev["adexl_run"]

    sch_diff = run_schematic_diff(prev_sch_num, curr_sch_num)

    prev_setup = load_adexl_setup_by_schematic_num(prev_sch_num)
    curr_setup = load_adexl_setup_by_schematic_num(curr_sch_num)
    setup_diff = diff_adexl_setup(prev_setup, curr_setup)

    adexl_diff = run_adexl_diff(prev_result_id, result_id)

    diff_text = build_diff_text(sch_diff, setup_diff, adexl_diff)
    history_text = build_recent_history_text(
        checkpoints,
        max_history=MAX_HISTORY_SHOWN
    )

    if use_gui:
        note = show_note_popup(diff_text, history_text, num_str)
    else:
        print(history_text)
        print("")
        print(diff_text)
        print("")
        note = prompt_note_terminal()

    if note is None:
        log("Checkpoint {0} cancelled by user.".format(num_str))
        print("Checkpoint cancelled. No report saved.")
        return

    if os.path.isfile(report_path):
        raise IOError("Report already exists, immutable: {0}".format(
            report_path
        ))

    report = {
        "checkpoint": num_str,
        "type": "comparison",
        "created_at": created_at,
        "schematic_prev": prev_sch_num,
        "schematic_curr": curr_sch_num,
        "adexl_prev": prev_result_id,
        "adexl_curr": result_id,
        "note": note,
        "schematic_diff": sch_diff,
        "adexl_setup_diff": setup_diff,
        "adexl_diff": adexl_diff,
    }

    write_json(report_path, report)

    entry = {
        "id": new_id,
        "type": "comparison",
        "tracker_checkpoint": num_str,
        "schematic_checkpoint": curr_sch_num,
        "schematic_file": os.path.basename(curr_sch_path),
        "adexl_run": result_id,
        "adexl_csv": os.path.basename(csv_path),
        "adexl_result_json": os.path.basename(result_json_path),
        "report": os.path.join("reports", report_filename),
        "timestamp": created_at,
        "note": note,
    }

    checkpoints.append(entry)
    save_index(index)

    log("Checkpoint {0} COMPARISON saved. Note: {1}".format(num_str, note))
    print("Checkpoint {0} COMPARISON saved.".format(num_str))

    if use_gui:
        show_success_popup(num_str, note)


# =====================================================================
# Commands
# =====================================================================

def parse_raw_axl_vars(raw_text):
    variables = {}

    for line in raw_text.splitlines():
        line = line.strip()

        if "=" not in line:
            continue

        name, value = line.split("=", 1)
        variables[name.strip()] = value.strip()

    return variables


def cmd_capture_adexl_setup(checkpoint_id, raw_file):
    ensure_dirs()

    if not os.path.isfile(raw_file):
        raise IOError("ADE XL raw vars file not found: {0}".format(raw_file))

    raw_handle = open(raw_file, "r")
    try:
        raw_text = raw_handle.read()
    finally:
        raw_handle.close()

    variables = parse_raw_axl_vars(raw_text)

    out_path = os.path.join(
        CHECKPOINTS_DIR,
        "{0}_adexl_setup.json".format(checkpoint_id)
    )

    data = {
        "checkpoint_id": checkpoint_id,
        "type": "adexl_setup",
        "variables": variables,
        "raw_file": os.path.basename(raw_file),
        "captured_at": now_str(),
    }

    write_json(out_path, data)

    log("Captured ADE XL setup for {0}: {1} variable(s)".format(
        checkpoint_id,
        len(variables)
    ))

    print("dtrace: captured ADE XL setup for {0}: {1} variable(s)".format(
        checkpoint_id,
        len(variables)
    ))


def cmd_set_pending():
    ensure_dirs()

    index = load_index()

    used = set()

    for entry in index["checkpoints"]:
        value = entry.get("schematic_checkpoint")

        if value is not None:
            used.add(value)

    state = load_state()

    if (
        state.get("pending") and
        state["pending"].get("schematic_checkpoint_num") is not None
    ):
        used.add(state["pending"].get("schematic_checkpoint_num"))

    curr_num, curr_path = find_latest_schematic_checkpoint(used)

    state["pending"] = {
        "schematic_checkpoint_num": curr_num,
        "schematic_file": os.path.basename(curr_path),
        "started_at": now_str(),
    }

    save_state(state)

    log("Pending set: checkpoint_{0:04d}".format(curr_num))
    print("dtrace: pending checkpoint_{0:04d} recorded.".format(curr_num))


def cmd_reference():
    ensure_dirs()

    index = load_index()

    for entry in index["checkpoints"]:
        if entry.get("type") == "schematic_reference":
            print("dtrace: schematic reference already exists as checkpoint_{0:04d}".format(
                entry.get("id", 0)
            ))
            log("Reference already exists; skipped.")
            return

    used = set(
        entry.get("schematic_checkpoint")
        for entry in index["checkpoints"]
        if entry.get("schematic_checkpoint") is not None
    )

    curr_num, curr_path = find_latest_schematic_checkpoint(used)

    new_id = len(index["checkpoints"])
    num_str = "{0:04d}".format(new_id)

    index["checkpoints"].append({
        "id": new_id,
        "type": "schematic_reference",
        "tracker_checkpoint": num_str,
        "schematic_checkpoint": curr_num,
        "schematic_file": os.path.basename(curr_path),
        "timestamp": now_str(),
        "note": None,
    })

    save_index(index)

    print("dtrace: checkpoint_{0} [SCHEMATIC REFERENCE] recorded.".format(
        num_str
    ))

    log("Reference baseline: checkpoint_{0} -> schematic checkpoint_{1:04d}".format(
        num_str,
        curr_num
    ))


def cmd_capture(use_gui=True):
    """
    Legacy debug path: complete checkpoint from latest Interactive.N.csv.
    """
    ensure_dirs()

    index = load_index()
    latest_csv = find_latest_adexl_csv()

    if latest_csv is None:
        print("ERROR: No Interactive.N.csv found in {0}".format(ADEXL_DOCS_DIR))
        sys.exit(1)

    run_num = extract_interactive_run_number(latest_csv)

    if run_num is None:
        print("ERROR: Could not extract Interactive run number from {0}".format(
            latest_csv
        ))
        sys.exit(1)

    used = set(
        entry.get("schematic_checkpoint")
        for entry in index["checkpoints"]
        if entry.get("schematic_checkpoint") is not None
    )

    curr_num, curr_path = find_latest_schematic_checkpoint(used)

    pending = {
        "schematic_checkpoint_num": curr_num,
        "schematic_file": os.path.basename(curr_path),
        "started_at": now_str(),
    }

    stable_csv, json_path = parse_explicit_csv_to_json(latest_csv, run_num)

    complete_checkpoint(
        pending,
        stable_csv,
        run_num,
        json_path,
        use_gui=use_gui
    )


def cmd_complete_csv(csv_path, use_gui=True):
    ensure_dirs()

    state = load_state()
    pending = state.get("pending")

    if not pending:
        print("ERROR: No pending schematic checkpoint found. Run dtraceRun() first.")
        sys.exit(1)

    index = load_index()
    result_id = next_result_id(index)

    try:
        stable_csv, json_path = parse_explicit_csv_to_json(csv_path, result_id)

        complete_checkpoint(
            pending,
            stable_csv,
            result_id,
            json_path,
            use_gui=use_gui
        )

    except Exception as error:
        log("ERROR complete-csv: {0}\n{1}".format(
            error,
            traceback.format_exc()
        ))
        print("ERROR: {0}".format(error))
        sys.exit(1)

    state = load_state()
    state["pending"] = None
    state["last_processed_run"] = result_id

    save_state(state)

    print("dtrace: complete-csv finished for result {0}".format(result_id))


def cmd_watch():
    """
    Legacy watcher for Interactive.N.csv flow.
    """
    ensure_dirs()

    pid_file = open(PID_PATH, "w")
    try:
        pid_file.write(str(os.getpid()) + "\n")
    finally:
        pid_file.close()

    log("Watcher started. Monitoring {0}".format(ADEXL_DOCS_DIR))

    while True:
        try:
            state = load_state()
            pending = state.get("pending")
            latest = find_latest_adexl_csv()

            if pending and latest and is_file_stable(latest):
                run_num = extract_interactive_run_number(latest)

                if (
                    run_num is not None and
                    run_num > state.get("last_processed_run", -1)
                ):
                    stable_csv, json_path = parse_explicit_csv_to_json(
                        latest,
                        run_num
                    )

                    complete_checkpoint(
                        pending,
                        stable_csv,
                        run_num,
                        json_path,
                        use_gui=True
                    )

                    state = load_state()
                    state["pending"] = None
                    state["last_processed_run"] = run_num
                    save_state(state)

        except Exception as error:
            log("Watcher error: {0}\n{1}".format(
                error,
                traceback.format_exc()
            ))

        time.sleep(POLL_INTERVAL_SEC)


def cmd_index():
    index = load_index()
    checkpoints = index.get("checkpoints", [])

    if not checkpoints:
        print("No checkpoints yet.")
        return

    print("")
    print("DTrace Index ({0} checkpoint(s))".format(len(checkpoints)))
    print("-" * 65)

    for entry in checkpoints:
        print("")
        print("checkpoint_{0:04d} [{1}] {2}".format(
            entry.get("id", 0),
            (entry.get("type") or "?").upper(),
            entry.get("timestamp", "?")
        ))
        print("  Schematic: {0}   Result: {1}".format(
            entry.get("schematic_checkpoint", "?"),
            entry.get("adexl_run", "(none)")
        ))
        print("  Note     : {0}".format(entry.get("note") or "(none)"))

        if entry.get("report"):
            print("  Report   : {0}".format(entry.get("report")))

    print("")


USAGE = """
DTrace - Engineering Traceability Framework

Commands:
  set-pending
      Record latest schematic checkpoint as pending.

  complete-csv <csv> [--no-gui]
      Complete pending checkpoint using explicit exported ADE XL CSV.

  capture [--no-gui]
      Manual debug path using latest Interactive.N.csv.

  reference
      Record schematic-only reference baseline.

  index
      Show checkpoint history.

  watch
      Legacy watcher for Interactive.N.csv flow.

  capture-adexl-setup <checkpoint_id> <raw_file>
      Convert raw ADE XL setup variables into JSON.
"""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        sys.exit(0)

    command = sys.argv[1]

    if command == "set-pending":
        cmd_set_pending()

    elif command == "reference":
        cmd_reference()

    elif command == "index":
        cmd_index()

    elif command == "watch":
        cmd_watch()

    elif command == "capture":
        cmd_capture(use_gui=("--no-gui" not in sys.argv))

    elif command == "complete-csv":
        args = [arg for arg in sys.argv[2:] if arg != "--no-gui"]

        if len(args) != 1:
            print("ERROR: Usage: python dtrace.py complete-csv <csv_path> [--no-gui]")
            sys.exit(1)

        cmd_complete_csv(args[0], use_gui=("--no-gui" not in sys.argv))

    elif command == "capture-adexl-setup":
        if len(sys.argv) != 4:
            print("ERROR: Usage: python dtrace.py capture-adexl-setup <checkpoint_id> <raw_file>")
            sys.exit(1)

        cmd_capture_adexl_setup(sys.argv[2], sys.argv[3])

    else:
        print("ERROR: Unknown command '{0}'".format(command))
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
