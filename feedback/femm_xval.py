"""Cross-validate the in-process solver against FEMM on a CLEAN slotless SPM
(same geometry fed to both). Slotless keeps the FEMM mesh light + the test fair:
it isolates the PM + steel + air-gap physics, which is the core to validate."""
import sys, time
sys.path.insert(0, ".")
import numpy as np
from shapely.geometry import Point
from litemaxwell.model.geometry import Shape
from litemaxwell.sample import build_motor
from litemaxwell.model.materials import default_library
from litemaxwell.model import apply_cmd
from litemaxwell.model.mesh import generate
from litemaxwell.model.solver import solve_magnetostatic
from litemaxwell.model import femm_backend as fb

POLES = 10
# start from the sample, then drop windings and make the stator a SOLID ring
full = build_motor(POLES, 12)
for s in full:
    apply_cmd(s)
shapes = [s for s in full if not s.name.startswith("Winding")]
ring = Point(0, 0).buffer(45, quad_segs=24).difference(Point(0, 0).buffer(26, quad_segs=24))
shapes = [Shape("Stator", ring, material="20PNX1200F", color="#8a939c")
          if s.name == "Stator" else s for s in shapes]
mats = default_library()
print(f"slotless SPM: {len(shapes)} shapes ({POLES} poles, solid stator)")

# --- internal solver ---
t = time.perf_counter()
mesh = generate(shapes, max_area=6.0)
f = solve_magnetostatic(mesh, shapes, mats, None, n_pole=POLES)
cm = mesh.nodes[mesh.triangles].mean(axis=1)
r = np.hypot(cm[:, 0], cm[:, 1]); gap = (r > 24) & (r < 26)
im, ix = float(f.Bmag[gap].mean()), float(f.Bmag[gap].max())
print(f"INTERNAL: airgap_B mean={im:.4f} max={ix:.4f} T  ({time.perf_counter()-t:.1f}s)")

# --- FEMM reference ---
t = time.perf_counter()
res = fb.solve(shapes, mats, n_pole=POLES, depth_mm=28.0, gap_samples=72)
print(f"FEMM    : airgap_B mean={res['airgap_B_mean']:.4f} max={res['airgap_B_max']:.4f} T  "
      f"({time.perf_counter()-t:.1f}s)")
ratio = im / res["airgap_B_mean"] if res["airgap_B_mean"] else 0
print(f"AGREEMENT mean ratio = {ratio:.3f}  (1.00 = perfect; 0.85-1.15 = good for lite FEA)")
