# DTrace Architecture

## Purpose

DTrace is an engineering traceability framework developed for analog IC design workflows in Cadence Virtuoso ADE XL.

Rather than replacing existing EDA tools, DTrace extends the normal design workflow by automatically recording engineering checkpoints throughout circuit development.

Each checkpoint combines:

* Schematic state
* ADE XL configuration
* Simulation results
* Differences from the previous checkpoint
* Designer rationale

The objective is to preserve engineering history rather than requiring designers to manually reconstruct why a circuit evolved over time.

---

# Design Objectives

The architecture was designed around several guiding principles.

## Preserve Existing Workflows

DTrace does not require designers to change how they perform simulations.

Instead, it integrates into an existing ADE XL workflow and records engineering information as simulations are executed.

---

## Local Execution

All processing occurs locally.

No cloud services, remote databases, or external servers are required.

All generated data remains inside the project directory.

---

## Separation of Responsibilities

Each module performs one clearly defined task.

The architecture separates:

* Cadence interaction
* Data extraction
* Data parsing
* Difference computation
* Report generation

This keeps the implementation modular and easier to maintain.

---

## Immutable Engineering History

Each completed checkpoint is stored as a permanent engineering record.

Rather than overwriting previous information, DTrace creates a new checkpoint for every completed iteration.

This makes it possible to reconstruct the complete design history.

---

# High-Level Architecture

```
Engineer
    │
    ▼
Cadence Virtuoso
    │
    ▼
ADE XL
    │
    ▼
SKILL Automation
    │
    ▼
CSV Export
    │
    ▼
Python Processing
    │
    ▼
JSON Checkpoints
    │
    ▼
Difference Engine
    │
    ▼
Engineering Report
```

The workflow consists of two primary layers.

* SKILL Layer
* Python Layer

Each layer has distinct responsibilities.

---

# SKILL Layer

The SKILL layer executes inside Cadence Virtuoso.

Its primary responsibilities are interacting with the design database and controlling the engineering workflow.

Major responsibilities include:

* Accessing the active ADE XL session
* Opening the current schematic
* Extracting schematic parameters
* Capturing ADE XL variables
* Exporting ADE XL result tables
* Launching Python processing
* Managing checkpoint creation

The SKILL layer does not perform engineering analysis.

Its role is limited to collecting information and initiating processing.

---

# Python Layer

The Python layer performs all post-processing.

Its responsibilities include:

* Parsing schematic snapshots
* Parsing ADE XL result exports
* Comparing checkpoints
* Detecting changes
* Building engineering reports
* Maintaining checkpoint history

Unlike the SKILL layer, Python operates entirely on exported data.

This separation reduces dependence on Cadence APIs once the required information has been captured.

---

# Major Components

## extractInstanceParams.il

Responsible for schematic extraction.

The script traverses the active schematic and records relevant instance parameters.

For MOS devices, parameters such as width, length, multiplier, finger width, and finger count are extracted.

The output becomes the raw schematic checkpoint.

---

## dtrace.il

Acts as the workflow controller.

Responsibilities include:

* Starting DTrace from ADE XL
* Capturing schematic checkpoints
* Capturing ADE XL variables
* Running simulations
* Exporting ADE XL results
* Invoking Python processing

This script forms the bridge between Virtuoso and the processing pipeline.

---

## schematic_tool.py

Processes exported schematic checkpoint CSV files.

Responsibilities include:

* Building structured JSON snapshots
* Comparing schematic checkpoints
* Detecting added instances
* Detecting removed instances
* Detecting modified parameters

The output becomes the schematic difference section of the checkpoint report.

---

## parse_adexl.py

Processes exported ADE XL result tables.

Responsibilities include:

* Reading exported CSV files
* Detecting result columns
* Parsing process and temperature information
* Parsing simulation metrics
* Producing structured JSON files

The parser is intentionally independent of circuit topology.

---

## diff_adexl_results.py

Compares parsed simulation result files.

Responsibilities include:

* Detecting regressions
* Detecting improvements
* Detecting value-only changes
* Tracking pass/fail transitions
* Comparing corner behaviour
* Building structured comparison data

The comparison engine evaluates differences between checkpoints but does not make engineering decisions.

---

## dtrace.py

Coordinates the complete processing flow.

Responsibilities include:

* Managing checkpoint state
* Coordinating parsers
* Building engineering reports
* Maintaining project history
* Saving comparison reports

This module represents the orchestration layer of DTrace.

---

# Data Flow

The information moves through several stages.

```
Schematic
        │
        ▼
CSV
        │
        ▼
JSON Snapshot
        │
        ▼
Comparison
        │
        ▼
Checkpoint Report
```

Simulation results follow a similar pipeline.

```
ADE XL
      │
      ▼
CSV Export
      │
      ▼
Parsed JSON
      │
      ▼
Comparison
      │
      ▼
Checkpoint Report
```

Keeping intermediate JSON files provides transparency and simplifies debugging.

---

# Checkpoint Lifecycle

Each engineering iteration follows the same lifecycle.

1. The designer modifies the circuit.

2. DTrace captures the current schematic state.

3. ADE XL variables are recorded.

4. ADE XL simulations execute.

5. Result tables are exported.

6. Python parses the exported data.

7. The current checkpoint is compared against the previous checkpoint.

8. The designer records a short engineering note.

9. A checkpoint report is generated.

10. The project history is updated.

Each completed checkpoint becomes part of the permanent engineering history.

---

# Generated Artifacts

A completed checkpoint produces several files.

| File                             | Purpose                       |
| -------------------------------- | ----------------------------- |
| checkpoint_xxxx.csv              | Raw schematic export          |
| checkpoint_xxxx.json             | Parsed schematic snapshot     |
| checkpoint_xxxx_adexl_setup.json | Parsed ADE XL variables       |
| checkpoint_xxxx_adexl_vars.raw   | Raw ADE XL variable export    |
| adexl_results_xxx.json           | Parsed simulation results     |
| checkpoint_xxxx_report.json      | Engineering checkpoint report |
| index.json                       | Project history               |
| dtrace.log                       | Execution log                 |

Each file represents one stage of the processing pipeline.

---

# Design Decisions

Several architectural decisions were made intentionally.

## CSV as the interchange format

CSV files are used as the interface between Cadence and Python.

This avoids direct dependence on Cadence database APIs during post-processing.

---

## JSON for structured storage

JSON provides a structured, human-readable representation of checkpoints and simulation data.

This makes reports easier to inspect and simplifies future automation.

---

## Event-Driven Execution

DTrace executes when the designer initiates a simulation.

There are no continuously running background services or monitoring processes.

This keeps resource usage low and aligns with the normal engineering workflow.

---

## Modular Components

Each module performs one clearly defined task.

This makes the framework easier to understand, debug, and extend.

---

# Scope

The current implementation focuses on:

* Cadence Virtuoso
* ADE XL
* SKILL automation
* Python-based processing
* Local engineering workflows
* Checkpoint-based design history

The framework is intentionally lightweight and avoids introducing additional infrastructure into the analog design environment.

---

# Summary

DTrace combines Cadence SKILL automation with Python-based data processing to create a persistent engineering history for analog circuit development.

Rather than replacing existing EDA tools, it augments the existing workflow by automatically capturing schematic evolution, simulation results, and engineering rationale at each checkpoint.

The result is a structured and reproducible record of the design process that can support debugging, design reviews, project handover, and long-term documentation.
