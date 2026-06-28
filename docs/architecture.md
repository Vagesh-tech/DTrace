# DTrace Architecture

## Overview

DTrace is a local engineering traceability framework for Cadence Virtuoso ADE XL.

It automatically captures schematic changes, simulation results, and engineering notes during analog circuit development, producing immutable checkpoint reports that document every design iteration.

The framework is designed to integrate into an existing Virtuoso workflow without requiring any modifications to Cadence itself.

---

## System Components

### SKILL Layer

Responsible for interacting with Cadence Virtuoso.

Functions include:

- Detecting active ADE XL sessions
- Capturing schematic checkpoints
- Exporting ADE XL result tables
- Exporting ADE XL variable settings
- Triggering Python processing
- Registering the F5 shortcut

---

### Python Layer

Responsible for data processing.

Modules include:

- schematic_tool.py
- parse_adexl.py
- diff_adexl_results.py
- dtrace.py

Responsibilities:

- Parse schematic snapshots
- Parse ADE XL results
- Compare consecutive checkpoints
- Detect parameter changes
- Rank simulation regressions
- Generate engineering reports

---

## Data Flow
Engineer
    │
    ▼
Press F5
    │
    ▼
SKILL captures schematic
    │
    ▼
ADE XL simulation
    │
    ▼
ADE XL exports results
    │
    ▼
Python parses outputs
    │
    ▼
Diff Engine
    │
    ▼
Checkpoint Report

---

## Design Principles

- Local execution only
- No external database
- No internet connectivity
- No modification of Cadence databases
- Immutable checkpoint history
- Modular Python architecture
- Separation of data capture and analysis
