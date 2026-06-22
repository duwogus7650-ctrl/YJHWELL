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
    coord_systems: list = field(default_factory=list)  # relative CS: {name,ox,oy,rot}
    symmetry_mult: int = 1                 # 2D Design Settings symmetry multiplier
    model_depth: float = 28.0              # model depth / stack length [mm]
    eddy_objects: list = field(default_factory=list)   # Set Eddy Effect: object names
    core_loss_objects: list = field(default_factory=list)  # Set Core Loss: object names
    use_skew: bool = False                 # 2D Design Settings: skew model on/off
    field_plots: list = field(default_factory=list)     # named field plots
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
    active_index: int = 0                   # which design is active (bold in tree)

    @property
    def active(self) -> Design:
        if not self.designs:
            self.designs.append(Design())
        self.active_index = max(0, min(self.active_index, len(self.designs) - 1))
        return self.designs[self.active_index]

    def add_design(self, design: Design, make_active: bool = True) -> Design:
        self.designs.append(design)
        if make_active:
            self.active_index = len(self.designs) - 1
        return design

    def copy_active(self, new_name: str) -> Design:
        """Duplicate the active design (Maxwell 'Copy Design') — deep copy so the
        new design's geometry/setup edit independently."""
        import copy
        d = copy.deepcopy(self.active)
        d.name = new_name
        return self.add_design(d)
