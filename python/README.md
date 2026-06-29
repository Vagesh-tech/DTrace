# Python Processing Engine

## Overview

This directory contains the Python processing layer of DTrace.

While the SKILL layer is responsible for interacting with Cadence Virtuoso and ADE XL, the Python layer performs all post-processing after data has been exported from the EDA environment.

The processing pipeline converts raw CSV exports into structured JSON data, compares engineering checkpoints, and generates engineering reports.

Each module has a clearly defined responsibility, allowing the processing pipeline to remain modular and maintainable.

---

# Directory Contents

```text
python/
├── dtrace.py
├── schematic_tool.py
├── parse_adexl.py
└── diff_adexl_results.py
```

---

# Module Overview

## dtrace.py

The orchestration module.

Responsibilities include:

* managing checkpoint state
* coordinating the processing pipeline
* generating engineering reports
* maintaining checkpoint history
* updating project metadata

This module serves as the central controller for the Python processing layer.

---

## schematic_tool.py

Processes schematic checkpoint data exported by the SKILL layer.

Responsibilities include:

* parsing schematic CSV files
* generating structured JSON snapshots
* comparing schematic checkpoints
* detecting added instances
* detecting removed instances
* detecting modified device parameters

The generated JSON becomes the schematic portion of each engineering checkpoint.

---

## parse_adexl.py

Processes simulation results exported from ADE XL.

Responsibilities include:

* reading exported CSV result tables
* identifying simulation outputs
* extracting corner information
* parsing process and temperature metadata
* generating structured JSON files

The parser is metric-agnostic and is not tied to a specific circuit topology.

---

## diff_adexl_results.py

Compares simulation results across checkpoints.

Responsibilities include:

* identifying regressions
* identifying improvements
* detecting value-only changes
* tracking pass/fail transitions
* comparing worst-corner behaviour
* preparing structured comparison data for report generation

The comparison engine records engineering differences without making design recommendations.

---

# Processing Pipeline

The Python layer follows a staged processing model.

```text
Raw CSV
    │
    ▼
Parser
    │
    ▼
Structured JSON
    │
    ▼
Comparison Engine
    │
    ▼
Checkpoint Report
```

Separating parsing from comparison keeps each module focused on a single task and simplifies future extensions.

---

# Design Philosophy

The Python modules intentionally avoid direct interaction with the Cadence design database.

Instead, they operate exclusively on exported data.

This separation provides several advantages:

* reduced dependence on Cadence APIs
* easier debugging
* transparent intermediate files
* reusable JSON representations
* modular processing stages

---

# Python Version

The implementation targets **Python 2.6** to remain compatible with the development environment used during the project.

No third-party Python packages are required.

---

# Summary

The Python layer forms the processing engine of DTrace.

It converts exported engineering data into structured checkpoints, compares design iterations, and generates the engineering reports that provide persistent traceability throughout the analog design workflow.
