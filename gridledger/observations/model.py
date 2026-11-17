from dataclasses import dataclass
from fractions import Fraction
from gridledger.grids.geometry import exact_value

MASS_UNIT = "mass"
FLUX_UNIT = "mass/time"

def record_identity(grid_id, cell_id, source_id):
    if isinstance(grid_id, bool) or not isinstance(grid_id, int) or grid_id <= 0:
        raise ValueError("invalid grid identity")
    if not isinstance(cell_id, (tuple, list)) or len(cell_id) != 2:
        raise ValueError("invalid cell identity")
    if any(isinstance(n, bool) or not isinstance(n, int) for n in cell_id):
        raise ValueError("cell indices must be integers")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("source identity must be nonempty")
    return tuple(cell_id)

@dataclass(frozen=True)
class MassRecord:
    grid_id: int
    cell_id: tuple[int, int]
    time: Fraction
    value: Fraction
    source_id: str
    unit: str = MASS_UNIT

    def __post_init__(self):
        object.__setattr__(self, "cell_id", record_identity(self.grid_id, self.cell_id, self.source_id))
        object.__setattr__(self, "time", exact_value(self.time))
        object.__setattr__(self, "value", exact_value(self.value))

    def logical_key(self):
        return self.grid_id, self.cell_id, self.time

@dataclass(frozen=True)
class FluxRecord:
    grid_id: int
    cell_id: tuple[int, int]
    side: str
    start: Fraction
    end: Fraction
    rate: Fraction
    source_id: str
    unit: str = FLUX_UNIT

    def __post_init__(self):
        object.__setattr__(self, "cell_id", record_identity(self.grid_id, self.cell_id, self.source_id))
        if not isinstance(self.side, str):
            raise ValueError("face side must be a string")
        for name in ("start", "end", "rate"):
            object.__setattr__(self, name, exact_value(getattr(self, name)))

    def logical_key(self):
        return self.grid_id, self.cell_id, self.side, self.start, self.end

@dataclass(frozen=True)
class ObservationRevision:
    id: int | None
    grid_id: int
    parent_id: int | None
    masses: tuple[MassRecord, ...]
    fluxes: tuple[FluxRecord, ...]
