"""Material definitions, including nonlinear B-H curves and PM properties.

Mirrors the Maxwell material features seen in the videos: a B-H table that can
be edited/imported/exported, permanent-magnet remanence/coercivity, and core
loss coefficients (Kh/Kc/Ke).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

MU0 = 4e-7 * np.pi


@dataclass
class BHCurve:
    """Nonlinear B-H magnetisation curve as a monotonic table."""

    H: np.ndarray = field(default_factory=lambda: np.array([], float))  # A/m
    B: np.ndarray = field(default_factory=lambda: np.array([], float))  # Tesla

    def is_empty(self) -> bool:
        return self.H.size == 0

    def mu_r_at(self, b: float) -> float:
        """Relative permeability interpolated at a given flux density."""
        if self.is_empty() or b <= 0:
            return 1.0
        h = float(np.interp(b, self.B, self.H))
        if h <= 0:
            return 1.0
        return b / (MU0 * h)

    @classmethod
    def from_rows(cls, rows: list[tuple[float, float]]) -> "BHCurve":
        if not rows:
            return cls()
        arr = np.asarray(sorted(rows), float)
        return cls(arr[:, 0], arr[:, 1])

    def rows(self) -> list[tuple[float, float]]:
        return [(float(h), float(b)) for h, b in zip(self.H, self.B)]

    def to_csv(self, path: str) -> None:
        np.savetxt(path, np.column_stack([self.H, self.B]),
                   delimiter=",", header="H(A/m),B(T)", comments="")

    @classmethod
    def from_csv(cls, path: str) -> "BHCurve":
        data = np.loadtxt(path, delimiter=",", skiprows=1)
        data = np.atleast_2d(data)
        return cls(data[:, 0], data[:, 1])


@dataclass
class Material:
    name: str
    color: str = "#cccccc"
    # linear fallback when no B-H curve is present
    mu_r: float = 1.0
    conductivity: float = 0.0          # S/m
    mass_density: float = 0.0          # kg/m^3
    bh: BHCurve = field(default_factory=BHCurve)
    # permanent magnet
    is_magnet: bool = False
    br: float = 0.0                    # remanence, T
    hc: float = 0.0                    # coercivity, A/m
    mag_dir_deg: float = 0.0           # magnetisation direction
    # core loss (Steinmetz-style) coefficients
    kh: float = 0.0
    kc: float = 0.0
    ke: float = 0.0

    @property
    def nonlinear(self) -> bool:
        return not self.bh.is_empty()


def system_library() -> list[tuple[str, str, str, "Material"]]:
    """Built-in material library for the Select Definition browser.
    Returns (name, location, origin, material). Includes the exact materials
    seen in the videos plus a few Granta entries for realism."""
    items: list[tuple[str, str, str, Material]] = []

    cu = Material("Copper (Pure)_80C", color="#d98c3f", mu_r=1.0,
                  conductivity=4.7092391e7, mass_density=8933)
    items.append((cu.name, "SysLibrary", "Granta Materials Data for Simulation", cu))

    mag = Material("Arnold_Magnetics_N45UH_80C", color="#c0392b", mu_r=1.05,
                   conductivity=6.7e5, mass_density=7500, is_magnet=True,
                   br=1.32, hc=1.0474e6)
    mag.bh = BHCurve.from_rows([(-1.35e6, -1.7558), (-1.0e6, -0.50),
                                (-0.5e6, 0.30), (0.0, 1.25)])
    items.append((mag.name, "SysLibrary", "ArnoldMagnetics", mag))

    steel = Material("20PNX1200F_20C", color="#8a939c", mu_r=4000,
                     conductivity=1.818e6, mass_density=7650,
                     kh=111.92, kc=0.1196, ke=2.828)
    steel.bh = BHCurve.from_rows([
        (0, 0.0), (50, 0.5), (100, 0.9), (200, 1.2), (400, 1.4),
        (800, 1.55), (2000, 1.7), (6000, 1.85), (20000, 2.0),
        (60000, 2.1), (150000, 2.2)])
    items.append((steel.name, "SysLibrary", "ChinaSteel", steel))

    for nm in ("Copper alloy, aluminum bronze, C95200, cast",
               "Copper alloy, aluminum bronze, CuAl10",
               "Copper alloy, C14500, hard",
               "Copper alloy, C15100", "Copper alloy, C18200",
               "Copper alloy, C64700", "Copper alloy, manganese bronze, C86300",
               "Copper beryllium alloy, C17000"):
        items.append((nm, "SysLibrary", "Granta Materials Data for Simulation",
                      Material(nm, color="#d98c3f", mu_r=1.0,
                               conductivity=2.0e7, mass_density=8000)))
    return items


def default_library() -> dict[str, Material]:
    """A small starter library covering the materials seen in the videos."""
    lib: dict[str, Material] = {}
    lib["vacuum"] = Material("vacuum", color="#eef1f4", mu_r=1.0)
    lib["air"] = Material("air", color="#eef1f4", mu_r=1.0)
    lib["copper"] = Material("copper", color="#d98c3f", mu_r=1.0,
                             conductivity=5.8e7, mass_density=8933)
    # electrical steel (placeholder linear-ish curve; editable in UI)
    steel = Material("20PNX1200F", color="#8a939c", mu_r=4000,
                     conductivity=1.1e6, mass_density=7650,
                     kh=180.0, kc=0.4, ke=0.0)
    steel.bh = BHCurve.from_rows([
        (0, 0.0), (50, 0.5), (100, 0.9), (200, 1.2), (400, 1.4),
        (800, 1.55), (2000, 1.7), (6000, 1.85), (20000, 2.0),
        (60000, 2.1), (150000, 2.2),
    ])
    lib[steel.name] = steel
    # NdFeB permanent magnet (N45UH-like)
    mag = Material("N45UH", color="#c0392b", mu_r=1.05, conductivity=6.7e5,
                   mass_density=7500, is_magnet=True, br=1.32, hc=1.0e6)
    lib[mag.name] = mag
    return lib
