from dataclasses import asdict, replace
import json
from gridledger.observations.model import MassRecord, FluxRecord, FluxFragment, ObservationRevision
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
        if candidate.flux_fragments is not None:
            for fragment in candidate.flux_fragments:
                connection.execute(
                    "INSERT INTO observation_flux_fragments(revision_id,source_id,start,end) "
                    "VALUES (?,?,?,?)",
                    (revision_id, fragment.record.source_id,
                     canonical_json(fragment.start), canonical_json(fragment.end)))
    return replace(candidate, id=revision_id)

def load_flux_fragments(connection, revision_id, fluxes):
    rows = connection.execute(
        "SELECT source_id,start,end FROM observation_flux_fragments WHERE revision_id=?",
        (revision_id,)).fetchall()
    if not rows:
        return None
    members = {record.source_id: record for record in fluxes}
    spans = {}
    fragments = []
    for source_id, start, end in rows:
        record = members.get(source_id)
        if record is None:
            raise ValueError("stored fragment without member source")
        start, end = decode_value(json.loads(start)), decode_value(json.loads(end))
        if not (record.start <= start < end <= record.end):
            raise ValueError("stored fragment outside source interval")
        spans.setdefault(source_id, []).append((start, end))
        fragments.append(FluxFragment(record, start, end))
    for source_id, pieces in spans.items():
        ordered = sorted(pieces)
        for (_, earlier_end), (later_start, _) in zip(ordered, ordered[1:]):
            if later_start < earlier_end:
                raise ValueError("stored fragments overlap for " + source_id)
    return tuple(sorted(fragments,
                        key=lambda f: (f.record.logical_key(), f.record.source_id, f.start, f.end)))

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
    fragments = load_flux_fragments(connection, revision_id, fluxes)
    return ObservationRevision(revision_id, row[0], row[1], masses, fluxes, fragments)
