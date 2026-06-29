# DTrace Workflow

## Purpose

DTrace is designed to integrate into the normal analog design workflow without changing how a designer interacts with Cadence Virtuoso or ADE XL.

Rather than introducing a new simulation environment, DTrace automatically records engineering checkpoints alongside the existing design process.

Each checkpoint represents one engineering iteration and captures both the technical changes and the reasoning behind them.

---

# Typical Design Iteration

During analog circuit development, a designer rarely reaches the final solution in a single simulation.

Instead, development consists of many iterations involving:

* transistor sizing
* compensation tuning
* bias adjustments
* ADE XL variable changes
* repeated simulation and verification

DTrace records each of these iterations as a permanent engineering checkpoint.

---

# Overall Workflow

The complete workflow is shown below.

```text
Engineer modifies schematic
        │
        ▼
Launch simulation from ADE XL
        │
        ▼
DTrace captures schematic snapshot
        │
        ▼
DTrace captures ADE XL variables
        │
        ▼
ADE XL executes simulations
        │
        ▼
ADE XL exports result table
        │
        ▼
Python parses exported data
        │
        ▼
Comparison with previous checkpoint
        │
        ▼
Designer enters engineering note
        │
        ▼
Checkpoint report generated
        │
        ▼
Project history updated
```

The designer continues working normally while DTrace records the engineering history in the background.

---

# Step 1 – Circuit Modification

The workflow begins when the designer modifies the circuit.

Typical modifications include:

* resizing transistors
* changing passive component values
* modifying compensation networks
* adjusting bias circuits
* updating ADE XL design variables

At this stage no checkpoint exists yet.

---

# Step 2 – Simulation Launch

The designer starts a normal ADE XL simulation.

This is the only action required to begin a new checkpoint.

DTrace integrates with the existing simulation flow rather than introducing a separate execution environment.

---

# Step 3 – Schematic Capture

Before simulation begins, DTrace captures the current schematic state.

Information recorded includes:

* instance names
* library names
* cell names
* view names
* selected device parameters

For MOS devices this includes:

* width
* length
* multiplier
* finger width
* finger count

The captured data is stored as a schematic checkpoint.

---

# Step 4 – ADE XL Setup Capture

DTrace records the active ADE XL design variables.

These variables represent the simulation configuration associated with the checkpoint.

Recording them ensures that changes in simulation setup become part of the engineering history.

---

# Step 5 – Simulation Execution

ADE XL performs the requested simulations.

DTrace does not interfere with Spectre or ADE XL.

Its role during this stage is simply to wait for completion before continuing the processing pipeline.

---

# Step 6 – Result Export

After simulation completes, ADE XL exports the result table.

The exported CSV becomes the input for the Python processing stage.

No manual export is required from the designer.

---

# Step 7 – Data Parsing

Python processes both exported datasets.

## Schematic parser

Converts:

```text
CSV
```

into

```text
Structured JSON
```

---

## ADE XL parser

Converts:

```text
ADE XL CSV
```

into

```text
Structured JSON
```

These JSON files become the canonical checkpoint representation.

---

# Step 8 – Checkpoint Comparison

DTrace compares the new checkpoint against the previous checkpoint.

Three independent comparisons are performed.

## Schematic comparison

Detects:

* added instances
* removed instances
* modified parameters

---

## ADE XL setup comparison

Detects:

* changed design variables
* added variables
* removed variables

---

## Simulation comparison

Detects:

* improvements
* regressions
* value changes
* pass/fail transitions
* worst-corner movement

The comparison process records differences only.

It does not attempt to judge whether a modification is correct or incorrect.

---

# Step 9 – Engineering Note

After comparison, the designer records a short engineering note.

Examples include:

* Increased pass-device width to reduce dropout.
* Reduced compensation capacitor to improve bandwidth.
* Updated load current for stability verification.

The note provides context that numerical results alone cannot capture.

---

# Step 10 – Report Generation

DTrace combines all collected information into a checkpoint report.

The report contains:

* checkpoint metadata
* schematic differences
* ADE XL setup differences
* simulation differences
* engineering note
* timestamps

This report becomes the permanent record of the engineering iteration.

---

# Project History

Each completed checkpoint is added to the project history.

Rather than replacing previous checkpoints, DTrace preserves every completed iteration.

This makes it possible to review the complete evolution of the design over time.

---

# Example Timeline

```text
Checkpoint 0001
│
├── Initial implementation
│
Checkpoint 0002
│
├── Compensation updated
│
Checkpoint 0003
│
├── Bias current modified
│
Checkpoint 0004
│
├── Stability improvement
│
Checkpoint 0005
│
└── Final verification
```

The exact number of checkpoints depends on the complexity of the project.

---

# Generated Files

A typical checkpoint produces files similar to:

```text
checkpoint_0007.csv
checkpoint_0007.json
checkpoint_0007_adexl_setup.json
checkpoint_0007_adexl_vars.raw
adexl_results_006.json
checkpoint_0007_report.json
index.json
```

Each file represents a different stage of the workflow.

Together they form a complete engineering record.

---

# Why This Workflow

The workflow was designed around three principles.

## Minimal disruption

Designers continue using Cadence Virtuoso and ADE XL exactly as before.

---

## Automatic documentation

Engineering information is captured automatically whenever a checkpoint is created.

---

## Reproducible design history

Every completed checkpoint records:

* what changed
* what happened
* why the change was made

This creates a permanent engineering history that supports debugging, design reviews, project handover, and long-term project documentation.

---

# Summary

DTrace integrates into the existing analog design workflow by automatically capturing schematic state, simulation configuration, simulation results, and engineering rationale for every design iteration.

Instead of replacing established EDA tools, it complements them by preserving the information that is typically lost between simulation runs, creating a structured and reproducible engineering history.
