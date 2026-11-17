from collections import defaultdict
from gridledger.grids.model import Face, FaceUse

SIDES = ("west", "east", "south", "north")

def build_faces(grid_id, cells):
    owners, geometry = defaultdict(list), {}
    for cell in cells:
        i, j = cell.id
        x0, y0, x1, y1 = cell.bounds
        definitions = (
            ("west", ("x", i, j), -1, ((x0, y0), (x0, y1))),
            ("east", ("x", i + 1, j), 1, ((x1, y0), (x1, y1))),
            ("south", ("y", i, j), -1, ((x0, y0), (x1, y0))),
            ("north", ("y", i, j + 1), 1, ((x0, y1), (x1, y1))),
        )
        for side, key, sign, endpoints in definitions:
            if key in geometry and geometry[key] != endpoints:
                raise ValueError("inconsistent shared face geometry")
            geometry[key] = endpoints
            owners[key].append(FaceUse(grid_id, cell.id, side, key, sign))
    return tuple(Face(grid_id, key, geometry[key], tuple(owners[key]))
                 for key in sorted(owners))

def cell_face_uses(grid, cell_id):
    grid.cell(cell_id)
    uses = [use for face in grid.faces for use in face.uses if use.cell_id == cell_id]
    return tuple(sorted(uses, key=lambda use: SIDES.index(use.side)))

def internal_face_pairs(grid):
    return tuple((face, face.uses[0], face.uses[1])
                 for face in grid.faces if len(face.uses) == 2)

def boundary_face_uses(grid):
    return tuple(face.uses[0] for face in grid.faces if len(face.uses) == 1)
