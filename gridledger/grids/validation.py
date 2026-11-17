from gridledger.grids.geometry import normalize_grid_spec, build_cells
from gridledger.grids.faces import build_faces, cell_face_uses, SIDES

def validate_grid_spec(name, shape, origin=(0, 0), spacing=(1, 1)):
    if not isinstance(name, str) or not name:
        raise ValueError("grid name must be nonempty")
    return normalize_grid_spec(shape, origin, spacing)

def validate_grid_revision(grid):
    spec = validate_grid_spec(grid.name, grid.shape, grid.origin, grid.spacing)
    expected_cells = build_cells(grid.id, *spec)
    if grid.cells != expected_cells or len({c.id for c in grid.cells}) != len(grid.cells):
        raise ValueError("cell identity or geometry mismatch")
    if any(c.area <= 0 for c in grid.cells):
        raise ValueError("nonpositive cell area")
    if grid.faces != build_faces(grid.id, grid.cells):
        raise ValueError("face identity or geometry mismatch")
    for cell in grid.cells:
        uses = cell_face_uses(grid, cell.id)
        if tuple(u.side for u in uses) != SIDES:
            raise ValueError("each cell must have four distinct sides")
    for face in grid.faces:
        if len(face.uses) not in (1, 2):
            raise ValueError("invalid face ownership")
        if len(face.uses) == 2 and sum(u.sign for u in face.uses) != 0:
            raise ValueError("internal directions must oppose")
    return grid
