# YJHWell — 2D PM Motor Design / Analysis

A lightweight, **offline** desktop clone of the Ansys Maxwell 2D workflow for
permanent-magnet motor design — modeler UI plus a real 2D magnetostatic
finite-element solver. Made by 여재현.

> Not a viewer: the solver assembles a sparse stiffness matrix `K`, solves
> `∇·(ν∇Az) = −Jz − ∇×M` with `scipy.sparse.linalg.spsolve`, and recovers
> `B = (∂Az/∂y, −∂Az/∂x)` per element. Results are checked against physics
> (air-gap flux density, dq torque theory) by the `feedback/` harness.

## Run it (offline, Windows)

First time (needs internet **once** to install dependencies):
```
setup.bat
```
Then launch the UI anytime, fully offline:
```
run.bat
```
Manual equivalent:
```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\pythonw run.py
```
Stack: Python 3.12 · PyQt6 · numpy/scipy · shapely · triangle · pyqtgraph.

## Features

- **Modeler** — ribbon UI, dual project/model trees, parametric variables
  (expression evaluation), draw (circle/rect/polyline/spline/arc), booleans,
  duplicate-around-axis/mirror, **relative coordinate systems** (offset + rotation,
  like Maxwell's Relative CS), material browser + B-H / B-P curve editors.
- **FEM solver** (`litemaxwell/model/solver.py`)
  - 2D magnetostatic, linear-triangle vector-potential formulation
  - permanent magnets (radial remanence source) + coil currents
  - **nonlinear B-H** (fixed-point reluctivity update, steel saturation)
  - **cogging torque** (Maxwell stress over an air-gap band)
  - **load torque** under synchronised 3-phase current
  - **back-EMF** — per-phase flux linkage `λ(θ)` → `e = −dλ/dt`
  - **core loss** — Steinmetz/Bertotti iron loss (hysteresis/eddy/excess)
  - **transient** — constant-speed time-domain back-EMF waveforms (vs time)
- **Results** — field overlay (Mag_B), Torque / Back-EMF / Load-Torque /
  Transient-EMF / Core-Loss, Optimetrics parametric sweep, CSV export.

## Design-agnostic

Pole count, slot count, speed, current, turns and geometry are all parameters —
the solver is **not** tied to any single design. The `feedback/` harness verifies
this with design-independent physics checks (3-phase balance, `e = −dλ/dt`
self-consistency, dq-vs-FEM torque agreement, `T ∝ I` linearity, nonlinear
linear-fallback identity) that hold across 8/10/14-pole machines and different
speeds, plus frozen regression baselines for the sample geometry.

## Verify the solver

```
python <feedback-runner>/scripts/runner.py --config feedback/feedback.config.json
```
Exit 0 = every metric within tolerance. See `feedback/` for the headless solve
case, oracle values and tolerances. Absolute machine constants (Kt, back-EMF
magnitude) should still be calibrated against Ansys Maxwell for a given design;
the harness verifies physics consistency and guards against regressions.

## Layout

| path | what |
|---|---|
| `run.py` / `run.bat` | entry point / launcher |
| `litemaxwell/model/` | geometry, materials, mesh, variables, **solver** |
| `litemaxwell/ui/` | main window, modeler view, ribbon, dialogs, results |
| `feedback/` | solver verification harness (solve case + oracle + config) |
| `docs/maxwell_ui_spec.md` | UI spec distilled from the design recordings |
| `tasks/` | todo + lessons |
