from dataclasses import asdict, replace
import json
from gridledger.observations.model import MassRecord, FluxRecord, ObservationRevision
from gridledger.archive.schema import archive_transaction
from gridledger.delivery.codec import canonical_json, decode_value

def record_body(record):
    return ("mass" if isinstance(record, MassRecord) else "flux"), canonical_json(asdict(record))

def load_source_record(connection, source_id):
    row = connection.execute("SELECT kind,body FROM sources WHERE source_id=?", (source_id,)).fetchone()
    if row is None:
        raise KeyError(source_id)
    if row[0] not in ("mass", "flux"):
        raise ValueError("invalid stored record kind")
    cls = MassRecord if row[0] == "mass" else FluxRecord
    return cls(**decode_value(json.loads(row[1])))

def save_observation_revision(connection, candidate):
    with archive_transaction(connection):
        cursor = connection.execute("INSERT INTO observation_revisions(grid_id,parent_id) VALUES (?,?)",
                                    (candidate.grid_id, candidate.parent_id))
        revision_id = cursor.lastrowid
        for record in candidate.masses + candidate.fluxes:
            kind, body = record_body(record)
            existing = connection.execute("SELECT grid_id,kind,body FROM sources WHERE source_id=?",
                                          (record.source_id,)).fetchone()
            if existing is None:
                connection.execute("INSERT INTO sources(source_id,grid_id,kind,body) VALUES (?,?,?,?)",
                                   (record.source_id, record.grid_id, kind, body))
            elif existing != (record.grid_id, kind, body):
                raise ValueError("stored source identity conflict")
            connection.execute("INSERT INTO observation_members(revision_id,source_id) VALUES (?,?)",
                               (revision_id, record.source_id))
    return replace(candidate, id=revision_id)

def load_observation_revision(connection, revision_id):
    row = connection.execute("SELECT grid_id,parent_id FROM observation_revisions WHERE id=?",
                             (revision_id,)).fetchone()
    if row is None:
        raise KeyError(revision_id)
    records = [load_source_record(connection, source_id) for (source_id,) in connection.execute(
        "SELECT source_id FROM observation_members WHERE revision_id=? ORDER BY source_id", (revision_id,))]
    masses = tuple(sorted((r for r in records if isinstance(r, MassRecord)), key=lambda r: r.logical_key()))
    fluxes = tuple(sorted((r for r in records if isinstance(r, FluxRecord)), key=lambda r: r.logical_key()))
    if any(r.grid_id != row[0] for r in records):
        raise ValueError("stored revision/grid binding mismatch")
    return ObservationRevision(revision_id, row[0], row[1], masses, fluxes)
