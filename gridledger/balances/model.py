from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class CellAccount:
    cell_id: tuple[int, int]
    mass_start: Fraction
    mass_end: Fraction
    change: Fraction
    faces: tuple
    outflow: Fraction
    residual: Fraction

@dataclass(frozen=True)
class BoundaryAccount:
    faces: tuple
    total_outflow: Fraction
    total_change: Fraction
    total_residual: Fraction

@dataclass(frozen=True)
class BalanceResult:
    grid_id: int
    observation_id: int
    plan_id: int | None
    cells: tuple[CellAccount, ...]
    boundary: BoundaryAccount
    anomalous_cells: tuple[tuple[int, int], ...]

    def validate(self):
        if len({c.cell_id for c in self.cells}) != len(self.cells):
            raise ValueError("duplicate cell account")
        for c in self.cells:
            if c.change != c.mass_end - c.mass_start:
                raise ValueError("incorrect mass change")
            if c.outflow != sum((f[2] for f in c.faces), Fraction(0)):
                raise ValueError("incorrect cell outflow")
            if c.residual != c.change + c.outflow:
                raise ValueError("incorrect residual")
        if self.anomalous_cells != tuple(c.cell_id for c in self.cells if c.residual != 0):
            raise ValueError("incorrect anomaly membership")
        if self.boundary.total_residual != sum((c.residual for c in self.cells), Fraction(0)):
            raise ValueError("incorrect global residual")
        return self
