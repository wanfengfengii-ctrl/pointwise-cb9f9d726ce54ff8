from dataclasses import asdict, replace
import json
from gridledger.observations.model import MassRecord, FluxRecord
from gridledger.windows.model import WindowPlan, SourceContribution
from gridledger.archive.schema import archive_transaction
from gridledger.delivery.codec import canonical_json, decode_value

def save_plan(connection, plan):
    body = asdict(replace(plan, id=None))
    with archive_transaction(connection):
        cursor = connection.execute("INSERT INTO plans(grid_id,observation_id,body) VALUES (?,?,?)",
                                    (plan.grid_id, plan.observation_id, canonical_json(body)))
        plan_id = cursor.lastrowid
    return replace(plan, id=plan_id)

def load_plan(connection, plan_id):
    row = connection.execute("SELECT grid_id,observation_id,body FROM plans WHERE id=?", (plan_id,)).fetchone()
    if row is None:
        raise KeyError(plan_id)
    data = decode_value(json.loads(row[2]))
    endpoints = tuple(tuple(MassRecord(**record) for record in pair) for pair in data.pop("endpoints"))
    contributions = []
    for item in data.pop("contributions"):
        item = dict(item)
        record = FluxRecord(**item.pop("record"))
        contributions.append(SourceContribution(record=record, **item))
    data["id"] = plan_id
    plan = WindowPlan(endpoints=endpoints, contributions=tuple(contributions), **data)
    if (plan.grid_id, plan.observation_id) != row[:2]:
        raise ValueError("stored plan binding mismatch")
    return plan

def publish_result(connection, snapshot):
    plan = load_plan(connection, snapshot["plan_id"])
    if (snapshot["grid_id"], snapshot["observation_id"], snapshot["window"]) != (
            plan.grid_id, plan.observation_id, [plan.a, plan.b]):
        raise ValueError("result/plan binding mismatch")
    header = dict(snapshot)
    cells, sources = header.pop("cells"), header.pop("sources")
    boundary = dict(header["boundary"])
    faces = boundary.pop("faces")
    header["boundary"] = boundary
    header["row_counts"] = [len(cells), len(faces), len(sources)]
    with archive_transaction(connection):
        cursor = connection.execute("INSERT INTO results(plan_id,header) VALUES (?,?)",
                                    (plan.id, canonical_json(header)))
        result_id = cursor.lastrowid
        for table, records in (("result_cells", cells), ("result_faces", faces), ("result_sources", sources)):
            for ordinal, record in enumerate(records):
                connection.execute("INSERT INTO " + table + "(result_id,ordinal,body) VALUES (?,?,?)",
                                   (result_id, ordinal, canonical_json(record)))
    return result_id

def load_result_rows(connection, result_id):
    root = connection.execute("SELECT plan_id,header FROM results WHERE id=?", (result_id,)).fetchone()
    if root is None:
        raise KeyError(result_id)
    header = decode_value(json.loads(root[1]))
    counts = header.pop("row_counts")
    if header["plan_id"] != root[0]:
        raise ValueError("stored result binding mismatch")
    children = []
    for table, count in zip(("result_cells", "result_faces", "result_sources"), counts):
        rows = connection.execute("SELECT ordinal,body FROM " + table +
                                  " WHERE result_id=? ORDER BY ordinal", (result_id,)).fetchall()
        if [r[0] for r in rows] != list(range(count)):
            raise ValueError("incomplete stored result")
        children.append([decode_value(json.loads(r[1])) for r in rows])
    if len(counts) != 3:
        raise ValueError("invalid result row counts")
    return header, *children
