from fractions import Fraction
from gridledger.grids.faces import boundary_face_uses, internal_face_pairs
from gridledger.balances.model import BoundaryAccount

def face_total(plan, use):
    return sum((c.integral for c in plan.face_contributions(use.cell_id, use.side)), Fraction(0))

def build_boundary_account(grid, plan, accounts):
    faces = tuple((use, face_total(plan, use)) for use in boundary_face_uses(grid))
    return BoundaryAccount(faces, sum((amount for _, amount in faces), Fraction(0)),
                           sum((c.change for c in accounts), Fraction(0)),
                           sum((c.residual for c in accounts), Fraction(0)))

def verify_global_identity(grid, plan, accounts, boundary):
    for _, left, right in internal_face_pairs(grid):
        if face_total(plan, left) + face_total(plan, right) != 0:
            raise ValueError("internal integrals do not cancel")
    if boundary.total_change != sum((c.change for c in accounts), Fraction(0)):
        raise ValueError("global mass change mismatch")
    if boundary.total_outflow != sum((amount for _, amount in boundary.faces), Fraction(0)):
        raise ValueError("boundary evidence mismatch")
    if boundary.total_residual != boundary.total_change + boundary.total_outflow:
        raise ValueError("global conservation identity violated")
