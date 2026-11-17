from gridledger.observations.model import MassRecord, MASS_UNIT

def validate_mass_batch(grid, records):
    seen = set()
    for record in records:
        if not isinstance(record, MassRecord):
            raise ValueError("expected MassRecord")
        if record.grid_id != grid.id:
            raise KeyError((record.grid_id, record.cell_id))
        grid.cell(record.cell_id)
        if record.unit != MASS_UNIT:
            raise ValueError("mass unit must be mass")
        if record.logical_key() in seen:
            raise ValueError("duplicate mass logical key")
        seen.add(record.logical_key())
    return tuple(records)

def index_masses(records):
    return {record.logical_key(): record for record in records}

def select_endpoint_masses(grid, records, a, b):
    index = index_masses(records)
    endpoints = []
    for cell in grid.cells:
        keys = ((grid.id, cell.id, a), (grid.id, cell.id, b))
        if any(key not in index for key in keys):
            raise ValueError("missing endpoint mass for " + str(cell.id))
        endpoints.append((index[keys[0]], index[keys[1]]))
    return tuple(endpoints)
