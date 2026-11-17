from gridledger.grids.geometry import exact_value
from gridledger.grids.faces import cell_face_uses
from gridledger.observations.masses import select_endpoint_masses
from gridledger.observations.fluxes import (effective_flux_fragments, index_flux_fragments,
                                            fragments_for_face)
from gridledger.windows.model import WindowPlan
from gridledger.windows.coverage import face_window_segments, require_exact_coverage
from gridledger.windows.integrals import integrate_face

def compile_window_plan(grid, observation, a, b):
    a, b = exact_value(a), exact_value(b)
    if a >= b:
        raise ValueError("window must satisfy a < b")
    if observation.grid_id != grid.id or observation.id is None:
        raise ValueError("observation/grid binding mismatch")
    endpoints = select_endpoint_masses(grid, observation.masses, a, b)
    fragments = index_flux_fragments(effective_flux_fragments(observation))
    contributions = []
    for cell in grid.cells:
        for use in cell_face_uses(grid, cell.id):
            segments = face_window_segments(fragments_for_face(fragments, use), a, b)
            require_exact_coverage(segments, a, b)
            contributions.extend(integrate_face(segments, use.face_id))
    return WindowPlan(grid.id, observation.id, a, b, endpoints, tuple(contributions))
