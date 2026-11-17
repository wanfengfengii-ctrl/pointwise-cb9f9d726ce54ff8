from gridledger.delivery.codec import canonical_json
from gridledger.delivery.results import copy_result_snapshot

def ordered_result_payload(snapshot):
    result = copy_result_snapshot(snapshot)
    result["cells"].sort(key=lambda c: c["cell"])
    result["anomalous_cells"].sort()
    for cell in result["cells"]:
        cell["faces"].sort(key=lambda f: (f["face"], f["side"]))
    result["boundary"]["faces"].sort(key=lambda f: (f["face"], f["cell"], f["side"]))
    result["sources"].sort(key=lambda s: (
        s["kind"], s["record"]["grid_id"], s["record"]["cell_id"],
        s["record"].get("side", ""), s["record"].get("time", s["record"].get("start")),
        s["record"]["source_id"]))
    return result

def write_result_json(snapshot, target):
    text = canonical_json(ordered_result_payload(snapshot)) + "\n"
    written = target.write(text)
    if written is not None and written != len(text):
        raise OSError("short result export write")
