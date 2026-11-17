from gridledger.grids.faces import cell_face_uses, internal_face_pairs
from gridledger.windows.coverage import require_exact_coverage, iter_common_intervals
from gridledger.windows.integrals import validate_contribution_total
from gridledger.balances.model import BalanceResult
from gridledger.balances.cell_accounts import build_cell_accounts, find_anomalous_cells
from gridledger.balances.boundary_accounts import build_boundary_account, verify_global_identity

def validate_internal_faces(grid, plan):
    for _, left, right in internal_face_pairs(grid):
        lhs = plan.face_contributions(left.cell_id, left.side)
        rhs = plan.face_contributions(right.cell_id, right.side)
        for start, end, lrecord, rrecord in iter_common_intervals(lhs, rhs):
            if lrecord.rate + rrecord.rate != 0:
                raise ValueError("internal face conflict on " + str((left.face_id, start, end,
                                                                    lrecord.source_id, rrecord.source_id)))

def execute_balance(grid, plan):
    if grid.id != plan.grid_id or plan.a >= plan.b:
        raise ValueError("invalid plan binding or window")
    count = 0
    for cell in grid.cells:
        for use in cell_face_uses(grid, cell.id):
            contributions = plan.face_contributions(cell.id, use.side)
            require_exact_coverage(contributions, plan.a, plan.b)
            for c in contributions:
                if c.face_id != use.face_id or c.record.grid_id != grid.id:
                    raise ValueError("contribution face binding mismatch")
            validate_contribution_total(contributions, sum(c.integral for c in contributions))
            count += len(contributions)
    if count != len(plan.contributions):
        raise ValueError("unexpected plan contributions")
    validate_internal_faces(grid, plan)
    cells = build_cell_accounts(grid, plan)
    boundary = build_boundary_account(grid, plan, cells)
    verify_global_identity(grid, plan, cells, boundary)
    return BalanceResult(grid.id, plan.observation_id, plan.id, cells, boundary,
                         find_anomalous_cells(cells)).validate()
