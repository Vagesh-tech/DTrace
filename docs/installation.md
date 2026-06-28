# Installation

## Requirements

- Cadence Virtuoso IC6.1.5
- ADE XL
- Python 2.6
- Linux

---

## Repository Layout
DTrace/

skill/
python/
images/
examples/
sample_reports/
docs/

---

## Installation Steps

1. Clone the repository.

2. Copy the SKILL files into your Cadence working directory.

3. Load the SKILL files from `.cdsinit`.

Example:
load("skill/extractInstanceParams.il")
load("skill/dtrace.il")


4. Copy the Python scripts to the configured location.

5. Update any required file paths inside the scripts.

6. Restart Cadence Virtuoso.

7. Open ADE XL.

8. Press **F5** to execute DTrace.

---

## Notes

This repository is intended as a reference implementation.

Depending on your Virtuoso installation, directory paths may need to be updated.
