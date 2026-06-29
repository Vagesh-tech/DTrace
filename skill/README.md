# SKILL Automation Layer

## Overview

This directory contains the Cadence Virtuoso automation layer of DTrace.

The SKILL scripts are responsible for interacting directly with the Virtuoso design database and ADE XL. They collect engineering data from the active design environment and initiate the Python processing pipeline.

Unlike the Python modules, which operate on exported files, the SKILL layer communicates directly with Cadence through the Virtuoso SKILL API.

Together, the SKILL and Python layers provide a complete engineering traceability workflow.

---

# Directory Contents

```text
skill/
├── extractInstanceParams.il
└── dtrace.il
```

---

# Script Overview

## extractInstanceParams.il

This script performs schematic extraction.

Its primary responsibility is to capture the current schematic state before simulation begins.

The extractor traverses the active schematic and records information required to reconstruct the engineering checkpoint.

Typical information includes:

* instance name
* library name
* cell name
* view name
* selected device parameters

For supported MOS devices, parameters such as:

* model
* width
* length
* multiplier
* finger width
* finger count

are exported as part of the checkpoint.

The extracted data is written to a CSV file and subsequently converted into structured JSON by the Python processing layer.

---

## dtrace.il

This script serves as the workflow controller.

It integrates DTrace into the Cadence Virtuoso ADE XL environment.

Major responsibilities include:

* obtaining the active ADE XL session
* creating new checkpoints
* capturing schematic data
* capturing ADE XL design variables
* launching ADE XL simulations
* exporting simulation results
* invoking the Python processing pipeline
* coordinating report generation

Rather than performing engineering analysis itself, the script acts as the bridge between Virtuoso and the Python processing engine.

---

# Interaction with Cadence

The SKILL layer operates entirely within Cadence Virtuoso.

Its interaction with the design environment includes:

* accessing the current cell view
* reading instance properties
* communicating with ADE XL
* exporting simulation data
* invoking external Python scripts

Once the required information has been exported, subsequent processing is delegated to the Python layer.

---

# Position Within the Architecture

The SKILL layer forms the front-end of the DTrace workflow.

```text
Engineer
      │
      ▼
Cadence Virtuoso
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
Engineering Report
```

This separation allows Cadence-specific functionality to remain isolated from the remainder of the processing pipeline.

---

# Design Principles

The SKILL implementation follows several design principles.

## Minimal Workflow Disruption

DTrace integrates into the existing Virtuoso and ADE XL workflow.

Designers continue using familiar simulation procedures while DTrace records engineering checkpoints automatically.

---

## Data Collection Only

The SKILL layer is responsible for collecting engineering information.

It does not perform:

* simulation result analysis
* report generation
* checkpoint comparison
* engineering decision making

These responsibilities belong to the Python processing layer.

---

## Clear Separation of Responsibilities

The architecture intentionally separates:

* data capture
* data parsing
* comparison
* report generation

This keeps each module focused on a single responsibility and simplifies maintenance.

---

# Generated Outputs

The SKILL layer produces the raw engineering artifacts consumed by the Python modules.

Typical outputs include:

```text
checkpoint_0007.csv
checkpoint_0007_adexl_vars.raw
dtrace_results_0006.csv
```

These files become the inputs for parsing, comparison, and report generation.

---

# Summary

The SKILL layer provides the interface between DTrace and Cadence Virtuoso.

By capturing schematic state, ADE XL configuration, and exported simulation data, it establishes the foundation upon which the remainder of the DTrace processing pipeline operates.

The separation between SKILL and Python keeps the framework modular while preserving compatibility with the existing Virtuoso workflow.
