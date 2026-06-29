# DTrace Installation

## Purpose

This document describes how to integrate DTrace into an existing Cadence Virtuoso ADE XL environment.

DTrace is not a standalone application. It extends an existing Virtuoso workflow using SKILL and Python.

The current implementation was developed and validated using:

* Cadence Virtuoso IC6.1.5
* ADE XL
* Python 2.6
* Linux

Other environments may require modifications to file paths or Cadence APIs.

---

# Requirements

Before installing DTrace, ensure the following software is available.

| Component          | Requirement      |
| ------------------ | ---------------- |
| Operating System   | Linux            |
| EDA Environment    | Cadence Virtuoso |
| Simulation Manager | ADE XL           |
| Scripting Language | SKILL            |
| Python             | Python 2.6       |

No additional third-party Python libraries are required.

---

# Repository Layout

After cloning the repository, the directory structure should resemble:

```text
DTrace/
├── docs/
├── examples/
├── images/
├── python/
├── sample_reports/
├── skill/
├── README.md
├── LICENSE
└── .gitignore
```

---

# Python Scripts

The Python directory contains the processing engine.

```text
python/
├── dtrace.py
├── schematic_tool.py
├── parse_adexl.py
└── diff_adexl_results.py
```

These scripts perform:

* schematic parsing
* ADE XL result parsing
* checkpoint comparison
* report generation

---

# SKILL Scripts

The SKILL directory contains the Virtuoso integration layer.

```text
skill/
├── extractInstanceParams.il
└── dtrace.il
```

These scripts:

* interact with Virtuoso
* access ADE XL
* export data
* invoke Python processing

---

# Configure File Paths

The supplied scripts contain local file paths used during development.

Typical examples include:

```text
/home/user/design_tracker/
/home/user/dtrace.py
```

These paths should be updated to match the local installation before running DTrace.

The required locations include:

* Python script locations
* DTrace working directory
* Report directory
* Checkpoint directory
* ADE XL export directory

---

# Load SKILL Files

Load the SKILL files from `.cdsinit`.

Example:

```skill
load("skill/extractInstanceParams.il")
load("skill/dtrace.il")
```

This makes the DTrace commands available inside Virtuoso.

---

# Working Directory

DTrace expects a writable working directory for generated artifacts.

Typical contents include:

```text
design_tracker/
├── checkpoints/
├── adexl_results/
├── reports/
├── dtrace.log
├── dtrace_state.json
└── index.json
```

These directories are created or updated as checkpoints are generated.

---

# Running DTrace

Open the target project in Cadence Virtuoso.

Open the associated ADE XL session.

Start the normal simulation workflow.

During execution DTrace will:

1. Capture the current schematic state.
2. Capture ADE XL setup variables.
3. Execute ADE XL simulations.
4. Export simulation results.
5. Parse generated data.
6. Compare against the previous checkpoint.
7. Generate an engineering checkpoint report.

No additional manual export steps are required during a normal workflow.

---

# Generated Outputs

After a successful checkpoint, the working directory contains artifacts similar to:

```text
checkpoint_0007.csv
checkpoint_0007.json
checkpoint_0007_adexl_setup.json
checkpoint_0007_adexl_vars.raw
adexl_results_006.json
checkpoint_0007_report.json
index.json
```

These files form the engineering history maintained by DTrace.

---

# Verification

A successful installation should allow the complete workflow to execute without errors.

Expected outputs include:

* schematic checkpoint
* parsed schematic JSON
* parsed ADE XL setup
* parsed ADE XL results
* checkpoint comparison report
* updated project history

The example files included in this repository can be used as references for the expected output format.

---

# Notes

DTrace is intended as an engineering workflow framework rather than a packaged software product.

Depending on the local Cadence installation, minor adjustments to file paths or environment-specific configuration may be required before use.

The architecture has intentionally been kept modular so that individual components can be adapted without changing the overall workflow.
