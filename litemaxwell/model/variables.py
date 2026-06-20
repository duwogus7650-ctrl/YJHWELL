"""Parametric design variables with expression evaluation — the way Maxwell
defines every dimension (e.g. D_ro=53.6, Radius='D_ro/2-T_m').

Values are unit-less millimetre magnitudes; expressions may reference other
variables and a small set of math functions. A 'deg' suffix is supported for
angles (converted to radians inside sin/cos via the deg()/rad helpers)."""
from __future__ import annotations

import math

_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "sqrt": math.sqrt, "abs": abs, "pi": math.pi, "PI": math.pi,
    "radians": math.radians, "degrees": math.degrees,
    "min": min, "max": max, "pow": pow, "exp": math.exp,
}


def _preprocess(expr: str) -> str:
    # '180deg' -> '(180*0.017453292519943295)'  ; 'mm'/'rpm' units stripped
    import re
    expr = re.sub(r'(?<![A-Za-z_])(\d+(?:\.\d+)?)\s*deg\b',
                  r'(\1*0.017453292519943295)', expr)
    expr = re.sub(r'\b(mm|rpm|A|deg)\b(?![A-Za-z_])', '', expr)
    return expr


class Variables:
    def __init__(self, initial: dict[str, str] | None = None):
        self.exprs: dict[str, str] = {}
        self._cache: dict[str, float] = {}
        for k, v in (initial or {}).items():
            self.exprs[k] = str(v)
        self.reevaluate()

    def set(self, name: str, expr: str):
        self.exprs[name] = str(expr)
        self.reevaluate()

    def delete(self, name: str):
        self.exprs.pop(name, None)
        self.reevaluate()

    def reevaluate(self):
        """Iteratively resolve variables that depend on each other."""
        vals: dict[str, float] = {}
        for _ in range(len(self.exprs) + 2):
            progressed = False
            for name, expr in self.exprs.items():
                if name in vals:
                    continue
                v = self._try_eval(expr, vals)
                if v is not None:
                    vals[name] = v; progressed = True
            if not progressed:
                break
        self._cache = vals

    def _try_eval(self, expr: str, vals: dict[str, float]):
        try:
            ns = dict(_FUNCS); ns.update(vals)
            return float(eval(_preprocess(str(expr)), {"__builtins__": {}}, ns))
        except Exception:
            return None

    def evaluate(self, expr: str) -> float:
        """Evaluate an expression against current variables. Raises ValueError."""
        v = self._try_eval(expr, self._cache)
        if v is None:
            raise ValueError(f"식 평가 실패: {expr}")
        return v

    def value(self, name: str, default: float = 0.0) -> float:
        return self._cache.get(name, default)

    def rows(self):
        out = []
        for name, expr in self.exprs.items():
            ev = self._cache.get(name)
            out.append((name, expr, "" if ev is None else f"{ev:g}"))
        return out


def default_variables() -> Variables:
    """The 400W 10-pole/12-slot variable set seen in the videos (subset)."""
    return Variables({
        "D_ro": "53.6", "T_m": "2.9", "D_shaft": "42", "N_pole": "10",
        "N_slot": "12", "g": "0.5", "T_yoke": "3.3", "D_so": "82.3",
        "D_si": "54.6", "W_so": "3", "L_stk": "28", "MagnetR": "1.9",
        "BaseRPM": "1000", "ini_pos": "-15",
    })
