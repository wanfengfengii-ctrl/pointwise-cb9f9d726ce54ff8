from dataclasses import dataclass
from fractions import Fraction
from gridledger.observations.model import MassRecord, FluxRecord

@dataclass(frozen=True)
class ClippedSegment:
    record: FluxRecord
    start: Fraction
    end: Fraction

@dataclass(frozen=True)
class SourceContribution:
    record: FluxRecord
    face_id: tuple[str, int, int]
    start: Fraction
    end: Fraction
    duration: Fraction
    integral: Fraction

@dataclass(frozen=True)
class WindowPlan:
    grid_id: int
    observation_id: int
    a: Fraction
    b: Fraction
    endpoints: tuple[tuple[MassRecord, MassRecord], ...]
    contributions: tuple[SourceContribution, ...]
    id: int | None = None

    def face_contributions(self, cell_id, side):
        return tuple(c for c in self.contributions
                     if c.record.cell_id == cell_id and c.record.side == side)
