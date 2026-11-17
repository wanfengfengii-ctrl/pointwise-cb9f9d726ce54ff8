from fractions import Fraction
from gridledger.grids.faces import cell_face_uses
from gridledger.balances.model import CellAccount

def build_cell_account(grid, plan, cell, endpoints):
    start, end = endpoints
    if (start.grid_id, start.cell_id, start.time) != (grid.id, cell.id, plan.a):
        raise ValueError("start endpoint binding mismatch")
    if (end.grid_id, end.cell_id, end.time) != (grid.id, cell.id, plan.b):
        raise ValueError("end endpoint binding mismatch")
    faces = []
    for use in cell_face_uses(grid, cell.id):
        amount = sum((c.integral for c in plan.face_contributions(cell.id, use.side)), Fraction(0))
        faces.append((use.face_id, use.side, amount))
    outflow = sum((f[2] for f in faces), Fraction(0))
    change = end.value - start.value
    return CellAccount(cell.id, start.value, end.value, change, tuple(faces), outflow, change + outflow)

def build_cell_accounts(grid, plan):
    if len(grid.cells) != len(plan.endpoints):
        raise ValueError("endpoint membership mismatch")
    return tuple(build_cell_account(grid, plan, cell, endpoints)
                 for cell, endpoints in zip(grid.cells, plan.endpoints))

def find_anomalous_cells(accounts):
    return tuple(account.cell_id for account in accounts if account.residual != 0)
