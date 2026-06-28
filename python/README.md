# DTrace Python Modules

This directory contains the Python components of the DTrace engineering traceability framework.

The modules are intentionally separated by responsibility to keep each part of the workflow independent and maintainable.

---

## dtrace.py

Main orchestration engine.

Responsibilities:

- Receives callbacks from Cadence SKILL
- Tracks pending checkpoints
- Coordinates complete checkpoint creation
- Invokes schematic and simulation comparison
- Generates immutable checkpoint reports
- Maintains project history
- Displays the designer note popup

This is the primary entry point used during normal operation.

---

## schematic_tool.py

Schematic parser and comparison engine.

Responsibilities:

- Parses exported schematic parameter CSV files
- Builds structured JSON snapshots
- Compares two schematic checkpoints
- Detects added, removed and modified devices
- Reports parameter-level changes

This module is completely independent of ADE XL.

---

## parse_adexl.py

ADE XL result parser.

Responsibilities:

- Reads ADE XL Detail View CSV exports
- Detects scalar result tables
- Extracts process and temperature metadata
- Parses corner values
- Produces structured JSON result files

Supports both exported CSV files and Interactive.N.csv parsing.

---

## diff_adexl_results.py

Simulation result comparison engine.

Responsibilities:

- Compares two parsed ADE XL result files
- Detects PASS/FAIL transitions
- Computes worst-corner movement
- Ranks result changes by magnitude
- Generates human-readable result summaries

The comparison engine is intentionally metric-agnostic and does not contain circuit-specific rules.

---

## Design Philosophy

Each module performs one clearly defined task.

```
Cadence SKILL
      │
      ▼
dtrace.py
      │
      ├────────► schematic_tool.py
      │
      ├────────► parse_adexl.py
      │
      └────────► diff_adexl_results.py
```

This separation makes the project easier to maintain, test, and extend while keeping individual modules focused on a single responsibility.
