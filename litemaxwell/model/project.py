"""Project / Design containers — the top of the data model tree."""
from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import Shape
from .materials import Material, default_library
from .mesh import Mesh
from .variables import Variables, default_variables


@dataclass
class Design:
    name: str = "Maxwell2DDesign1"
    solver: str = "Magnetostatic"          # Magnetostatic | Transient
    shapes: list[Shape] = field(default_factory=list)
    mesh: Mesh | None = None
    # --- analysis setup (v2) ---
    excitations: list[dict] = field(default_factory=list)
    boundaries: list[dict] = field(default_factory=list)
    mesh_ops: list[dict] = field(default_factory=list)
    motion: dict | None = None
    setup: dict | None = None
    field: object = None                   # solved field result (Field)

    def add(self, shape: Shape) -> Shape:
        self.shapes.append(shape)
        return shape

    def remove(self, shape: Shape) -> None:
        if shape in self.shapes:
            self.shapes.remove(shape)

    def find(self, name: str) -> Shape | None:
        return next((s for s in self.shapes if s.name == name), None)


@dataclass
class Project:
    name: str = "Untitled"
    designs: list[Design] = field(default_factory=lambda: [Design()])
    materials: dict[str, Material] = field(default_factory=default_library)
    variables: Variables = field(default_factory=default_variables)

    @property
    def active(self) -> Design:
        return self.designs[0]
