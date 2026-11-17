from fractions import Fraction
from gridledger.grids.model import Cell

def exact_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError("expected int or Fraction")
    return Fraction(value)

def pair(value, label):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(label + " must have two entries")
    return tuple(exact_value(x) for x in value)

def normalize_grid_spec(shape, origin=(0, 0), spacing=(1, 1)):
    shape = pair(shape, "shape")
    if any(n.denominator != 1 or n <= 0 for n in shape):
        raise ValueError("shape must contain positive integral counts")
    origin, spacing = pair(origin, "origin"), pair(spacing, "spacing")
    if any(d <= 0 for d in spacing):
        raise ValueError("spacing must be positive")
    return tuple(int(n) for n in shape), origin, spacing

def cell_bounds(cell_id, origin, spacing):
    i, j = cell_id
    x, y = origin
    dx, dy = spacing
    return x + i * dx, y + j * dy, x + (i + 1) * dx, y + (j + 1) * dy

def build_cells(grid_id, shape, origin, spacing):
    return tuple(Cell(grid_id, (i, j), cell_bounds((i, j), origin, spacing))
                 for i in range(shape[0]) for j in range(shape[1]))
