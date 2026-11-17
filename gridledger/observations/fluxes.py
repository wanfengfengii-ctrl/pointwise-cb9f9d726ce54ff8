from collections import defaultdict
from gridledger.grids.faces import cell_face_uses
from gridledger.observations.model import FluxRecord, FLUX_UNIT

def validate_flux_batch(grid, records):
    seen = set()
    for record in records:
        if not isinstance(record, FluxRecord):
            raise ValueError("expected FluxRecord")
        if record.grid_id != grid.id:
            raise KeyError((record.grid_id, record.cell_id, record.side))
        uses = cell_face_uses(grid, record.cell_id)
        if record.side not in {use.side for use in uses}:
            raise KeyError((grid.id, record.cell_id, record.side))
        if record.unit != FLUX_UNIT or record.start >= record.end:
            raise ValueError("invalid flux unit or interval")
        if record.logical_key() in seen:
            raise ValueError("duplicate flux logical key")
        seen.add(record.logical_key())
    return tuple(records)

def index_fluxes(records):
    index = defaultdict(list)
    for record in records:
        index[(record.grid_id, record.cell_id, record.side)].append(record)
    return {key: tuple(sorted(items, key=lambda r: (r.start, r.end, r.source_id)))
            for key, items in index.items()}

def records_for_face(index, use):
    return index.get((use.grid_id, use.cell_id, use.side), ())
