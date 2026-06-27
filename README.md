# DTrace

![DTrace Hero Banner](images/01-hero-banner.png)

Engineering Traceability Framework for Analog IC Design

DTrace is an engineering traceability framework for Cadence Virtuoso ADE XL that automatically captures schematic snapshots, compares simulation results across iterations, records engineering rationale, and builds an immutable design history using SKILL and Python.

---

# Why DTrace?

Traditional analog design workflows rely heavily on an engineer's memory.

After dozens of design iterations it becomes difficult to answer questions such as:

- Which transistor sizing caused this improvement?
- Which simulation introduced this regression?
- When did the worst corner change?
- Why was this bias current modified?
- What was the reasoning behind this compensation change?

DTrace automatically records every engineering iteration so the complete design history is permanently preserved.

![Workflow Comparison](images/04-comparison.png)

---

# System Architecture

The framework consists of four major components that work together to capture, analyze, compare, and archive every design iteration.

- ADE XL executes simulations.
- SKILL captures schematic state automatically.
- Python parses and compares simulation results.
- Engineering History stores immutable checkpoint reports.

![System Architecture](images/01-system-architecture_2.png)

---

# Getting Started

DTrace integrates directly into the normal ADE XL workflow without requiring engineers to change their existing simulation process.

![Quick Start](images/02-quickstart.png)

---

# Features

Core capabilities provided by DTrace include:

- Automatic schematic capture before simulation
- Automatic simulation result comparison
- Parameter-level schematic diff
- Worst-corner analysis
- Regression detection
- Engineering note recording
- Immutable checkpoint history

![Feature Overview](images/06-features.png)

---

# Engineering History

Every design iteration becomes a permanent checkpoint that can be revisited at any time.

Each checkpoint stores:

- Schematic snapshot
- Simulation results
- Schematic differences
- Performance differences
- Engineering rationale

![Engineering Timeline](images/05-timeline.png)

---

# Repository Structure

The repository is organized into separate SKILL, Python, documentation, and report components.

![Repository Structure](images/03-repo-structure.png)

---

# Repository Layout

```
DTrace/
├── docs/
├── examples/
├── images/
├── python/
├── sample_reports/
├── scripts/
├── skill/
├── tests/
├── .gitignore
├── LICENSE
└── README.md
```

---

# Technology Stack

- Cadence Virtuoso IC6.1.5
- ADE XL
- SKILL
- Python 2.6
- JSON
- CSV
- File-system based storage

---

# License

Released under the MIT License.
