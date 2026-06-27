# DTrace

![DTrace Hero Banner](images/01-hero-banner.png)

<p align="center">
  <img src="https://img.shields.io/badge/Cadence-Virtuoso-blue" />
  <img src="https://img.shields.io/badge/ADE%20XL-Integration-teal" />
  <img src="https://img.shields.io/badge/SKILL-Automation-green" />
  <img src="https://img.shields.io/badge/Python-2.6-yellow" />
  <img src="https://img.shields.io/badge/Storage-File%20System-lightgrey" />
  <img src="https://img.shields.io/badge/License-MIT-brightgreen" />
</p>

**DTrace** is an engineering traceability framework for **Cadence Virtuoso ADE XL**. It captures schematic checkpoints, parses simulation results, compares design iterations, records engineering rationale, and builds an immutable engineering history using **SKILL** and **Python**.

DTrace is built around one principle:

> **Historian, not Advisor.**  
> DTrace records what changed and preserves engineering intent. It does not recommend design changes or replace analog design judgement.

---

## Contents

- [Why DTrace?](#why-dtrace)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Features](#features)
- [Engineering History](#engineering-history)
- [Repository Structure](#repository-structure)
- [Example Output](#example-output)
- [Project Status](#project-status)
- [Limitations](#limitations)
- [License](#license)

---

## Why DTrace?

Traditional analog IC design workflows rely heavily on manual tracking.

After many design iterations, it becomes difficult to answer questions such as:

- Which schematic change caused this result shift?
- When did a regression first appear?
- Which corner became the new worst case?
- Why was this bias current, device size, or compensation value changed?
- Which simulation result corresponds to which schematic state?

DTrace solves this by preserving the full engineering context of each iteration.

![Traditional Workflow vs DTrace](images/04-comparison.png)

---

## System Architecture

DTrace separates the workflow into four layers:

1. **ADE XL** runs the designer's existing simulation setup.
2. **SKILL** captures schematic state and interfaces with Cadence.
3. **Python** parses, compares, and generates reports.
4. **Engineering History** stores immutable checkpoint records.

![System Architecture](images/01-system-architecture_2.png)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Design Environment | Cadence Virtuoso IC6.1.5 |
| Simulation Manager | ADE XL |
| Cadence Automation | SKILL |
| Processing Engine | Python 2.6 |
| Data Exchange | CSV |
| Storage | JSON + file system |
| License | MIT |

DTrace does **not** require:

- cloud services
- databases
- internet access
- external Python libraries

It is designed to run inside the existing Cadence design environment.

---

## Getting Started

The normal workflow is:

1. Copy SKILL files into the Cadence environment.
2. Copy Python scripts into the working directory.
3. Load the SKILL entry point through `.cdsinit`.
4. Open ADE XL.
5. Start the DTrace run flow.
6. Review the comparison popup.
7. Save the checkpoint.

![Quick Start](images/02-quickstart.png)

> Detailed setup instructions will be added as the repository is cleaned and packaged.

---

## Features

DTrace provides four core capabilities:

- **Automatic Capture**
  - schematic checkpoint capture
  - ADE XL result export capture

- **Comparison Engine**
  - schematic diff
  - simulation result diff
  - regression detection
  - worst-corner tracking

- **Engineering Documentation**
  - designer rationale captured per checkpoint
  - immutable checkpoint reports

- **History Management**
  - sequential checkpoint history
  - file-system based archive
  - JSON reports

![Feature Overview](images/06-features.png)

---

## Engineering History

Each design iteration becomes a permanent checkpoint.

A checkpoint may contain:

- schematic snapshot
- ADE XL setup state
- simulation results
- schematic diff
- result diff
- engineering note
- checkpoint report

![Engineering History Timeline](images/05-timeline.png)

---

## Repository Structure

![Repository Structure](images/03-repo-structure.png)

```text
DTrace/
├── docs/
│   └── Engineering notebook, setup notes, and documentation
│
├── examples/
│   └── Sample schematic/result files for reference
│
├── images/
│   └── README figures and documentation images
│
├── python/
│   └── Python parsing, comparison, and checkpoint scripts
│
├── sample_reports/
│   └── Example generated checkpoint reports
│
├── scripts/
│   └── Helper scripts
│
├── skill/
│   └── Cadence SKILL integration files
│
├── tests/
│   └── Future regression tests
│
├── .gitignore
├── LICENSE
└── README.md
````

---

## Example Output

DTrace generates checkpoint reports that combine:

* modified schematic parameters
* simulation result changes
* pass/fail transitions
* worst-corner movement
* engineering note
* timestamp and checkpoint metadata

Example checkpoint reports will be added under:

```text
sample_reports/
```

---

## Project Status

Current repository status:

* Documentation structure completed
* Visual assets completed
* Repository structure created
* SKILL and Python source upload in progress
* Sample reports to be added
* Setup guide to be added

This repository is being prepared as a public portfolio-quality engineering project.

---

## Limitations

Current known limitations:

* Developed and validated in Cadence Virtuoso IC6.1.5
* Python 2.6 compatibility maintained due to Cadence environment
* Designed for ADE XL workflow
* Not validated on Maestro
* Top-level schematic extraction only in current version
* File paths may require local configuration before reuse

---

## Documentation

The full engineering design notebook documents:

* motivation
* requirements
* architecture
* implementation
* engineering decisions
* debugging history
* validation
* limitations
* future work

The notebook will be added under:

```text
docs/
```

---

## License

This project is released under the MIT License.

---

## Author

**Vagish Revankar**

Analog / Mixed-Signal IC Design
Cadence Virtuoso • ADE XL • SKILL • Python • EDA Automation

```
```
