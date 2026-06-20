"""Parametric design variables with expression evaluation — the way Maxwell
defines every dimension (e.g. D_ro=53.6, theta_two='asin(...)').

Angles are handled in DEGREES (Maxwell convention): the trig functions take/
return degrees and a 'deg' suffix is just a unit tag, so evaluated values match
Maxwell's Properties → Variables display exactly.
"""
from __future__ import annotations

import math
import re

_FUNCS = {
    # degree-based trig (argument in degrees; inverse returns degrees)
    "sin": lambda x: math.sin(math.radians(x)),
    "cos": lambda x: math.cos(math.radians(x)),
    "tan": lambda x: math.tan(math.radians(x)),
    "asin": lambda x: math.degrees(math.asin(x)),
    "acos": lambda x: math.degrees(math.acos(x)),
    "atan": lambda x: math.degrees(math.atan(x)),
    "atan2": lambda y, x: math.degrees(math.atan2(y, x)),
    "sqrt": math.sqrt, "abs": abs, "exp": math.exp,
    "min": min, "max": max, "pow": pow,
    "pi": math.pi, "PI": math.pi,
}

_UNIT_SUFFIX = re.compile(r'(\d(?:[\d.]*\d)?)\s*(deg|mm|cm|rpm|rps|kg|Hz|Wb|A|H|s|V|T)\b',
                          re.IGNORECASE)
_UNIT_WORD = re.compile(r'\b(deg|mm|cm|rpm|rps)\b', re.IGNORECASE)


def _preprocess(expr: str) -> str:
    expr = str(expr)
    expr = _UNIT_SUFFIX.sub(r'\1', expr)     # 180deg -> 180, 3000rpm -> 3000
    expr = _UNIT_WORD.sub('', expr)
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
        vals: dict[str, float] = {}
        for _ in range(len(self.exprs) + 3):
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

    def _try_eval(self, expr, vals):
        try:
            ns = dict(_FUNCS); ns.update(vals)
            return float(eval(_preprocess(expr), {"__builtins__": {}}, ns))
        except Exception:
            return None

    def evaluate(self, expr: str) -> float:
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
    """The full 400W 10-pole/12-slot design variable set from the videos."""
    return Variables({
        "D_ro": "53.6", "T_m": "2.9", "D_shaft": "42", "N_pole": "10",
        "a_m": "0.89",
        "theta_one": "180deg/N_pole*a_m",
        "Magnet_R_Offset": "10",
        "theta_two": "asin((D_ro/2-T_m)*sin(theta_one)/(D_ro/2-Magnet_R_Offset))",
        "MagnetR": "1.9", "D_so": "82.3", "T_yoke": "3.3", "g": "0.5",
        "D_si": "D_ro+2*g", "d_1": "0.8", "N_slot": "12", "W_so": "3",
        "theta_so2": "2*asin(W_so/(2*(D_si/2+d_1)))",
        "theta_ss2": "360deg/N_slot-theta_so2",
        "theta_so": "2*asin(W_so/(2*(D_si/2)))",
        "theta_ss": "360deg/N_slot-theta_so",
        "d_2": "0.5", "W_t": "5.6",
        "theta_st": "2*asin(W_t/(2*(D_si/2+d_1+d_2)))",
        "H_t": "(D_so/2-T_yoke)-(D_si/2+d_1+d_2)",
        "ini_pos": "-15", "BaseRPM": "3000", "I_rms": "8.2",
        "Ia_max": "I_rms*sqrt(2)",
        "omega": "2*PI*BaseRPM/60RPM*N_pole/2",
        "a": "1", "Zc": "14",
        "stop_time": "120RPM/(BaseRPM*N_pole)",
        "time_step": "stop_time/36",
        "L_stk": "28",
        "theta_x1": "asin((W_t/2)/(D_so/2-T_yoke))",
    })
