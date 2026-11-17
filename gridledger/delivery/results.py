from copy import deepcopy
from dataclasses import asdict
from gridledger.delivery.codec import RESULT_FORMAT_VERSION

def verify_result_binding(plan, result):
    if plan.id is None or (plan.grid_id, plan.observation_id, plan.id) != (
            result.grid_id, result.observation_id, result.plan_id):
        raise ValueError("result does not belong to fixed plan")
    result.validate()

def build_result_snapshot(plan, result):
    verify_result_binding(plan, result)
    sources = []
    for pair in plan.endpoints:
        for record in pair:
            sources.append({"kind": "mass", "record": asdict(record)})
    for c in plan.contributions:
        sources.append({"kind": "flux", "record": asdict(c.record), "face": list(c.face_id),
                        "clipped": [c.start, c.end], "duration": c.duration, "integral": c.integral})
    cells = []
    for c in result.cells:
        cells.append({"cell": list(c.cell_id), "mass_start": c.mass_start, "mass_end": c.mass_end,
                      "change": c.change, "outflow": c.outflow, "residual": c.residual,
                      "faces": [{"face": list(face), "side": side, "integral": amount}
                                for face, side, amount in c.faces]})
    boundary = result.boundary
    return {"format_version": RESULT_FORMAT_VERSION, "grid_id": result.grid_id,
            "observation_id": result.observation_id, "plan_id": result.plan_id,
            "window": [plan.a, plan.b], "cells": cells,
            "anomalous_cells": [list(cell) for cell in result.anomalous_cells],
            "boundary": {"faces": [{"face": list(use.face_id), "cell": list(use.cell_id),
                                    "side": use.side, "integral": amount}
                                   for use, amount in boundary.faces],
                         "total_outflow": boundary.total_outflow, "total_change": boundary.total_change,
                         "total_residual": boundary.total_residual},
            "sources": sources}

def restore_result_snapshot(rows):
    header, cells, faces, sources = rows
    if header["format_version"] != RESULT_FORMAT_VERSION:
        raise ValueError("unsupported result format")
    snapshot = deepcopy(header)
    snapshot["cells"], snapshot["sources"] = deepcopy(cells), deepcopy(sources)
    snapshot["boundary"]["faces"] = deepcopy(faces)
    return snapshot

def copy_result_snapshot(snapshot):
    return deepcopy(snapshot)
