import json
from gridledger.grids.model import GridRevision
from gridledger.grids.geometry import build_cells
from gridledger.grids.faces import build_faces
from gridledger.grids.validation import validate_grid_spec, validate_grid_revision
from gridledger.archive.schema import archive_transaction
from gridledger.delivery.codec import canonical_json, decode_value

def assemble_grid(grid_id, name, spec):
    cells = build_cells(grid_id, *spec)
    grid = GridRevision(grid_id, name, *spec, cells, build_faces(grid_id, cells))
    return validate_grid_revision(grid)

def save_grid_revision(connection, name, shape, origin=(0, 0), spacing=(1, 1)):
    spec = validate_grid_spec(name, shape, origin, spacing)
    assemble_grid(0, name, spec)
    with archive_transaction(connection):
        cursor = connection.execute("INSERT INTO grid_revisions(name,spec) VALUES (?,?)",
                                    (name, canonical_json(spec)))
        grid = assemble_grid(cursor.lastrowid, name, spec)
    return grid.id

def load_grid_revision(connection, grid_id):
    row = connection.execute("SELECT name,spec FROM grid_revisions WHERE id=?", (grid_id,)).fetchone()
    if row is None:
        raise KeyError(grid_id)
    return assemble_grid(grid_id, row[0], decode_value(json.loads(row[1])))
