# Workflow

## Typical Engineering Flow

1. Modify the schematic.

2. Press **F5**.

3. DTrace captures the schematic checkpoint.

4. ADE XL simulations execute.

5. Results are exported automatically.

6. Python parses schematic and simulation data.

7. Differences from the previous checkpoint are computed.

8. A checkpoint report is generated.

9. The engineer records the design rationale.

10. The checkpoint becomes part of the permanent engineering history.

---

## Generated Artifacts

For every checkpoint DTrace generates:

- Schematic snapshot
- ADE XL variable snapshot
- Parsed simulation results
- Schematic difference report
- Simulation difference report
- Engineering checkpoint report

---

## Typical Use Cases

- Design iteration tracking
- Regression detection
- Documentation of engineering decisions
- Review preparation
- Project handover
- Debug history reconstruction

---

## Philosophy

The goal of DTrace is not to replace Cadence.

Instead, it adds persistent engineering traceability to an existing analog design workflow while requiring minimal disruption to the designer's normal process.
