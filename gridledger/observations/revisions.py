from collections import defaultdict
from gridledger.observations.model import ObservationRevision, FluxFragment
from gridledger.observations.masses import validate_mass_batch
from gridledger.observations.fluxes import validate_flux_batch

def validate_source_bindings(records, existing):
    bindings = dict(existing)
    for record in records:
        if record.source_id in bindings and bindings[record.source_id] != record:
            raise ValueError("source identity cannot be redefined: " + record.source_id)
        bindings[record.source_id] = record

def subtract_window(fragments, start, end):
    remainder = []
    for x, y in fragments:
        lo = min(max(x, start), y)
        hi = max(min(y, end), x)
        if x < lo:
            remainder.append((x, lo))
        if hi < y:
            remainder.append((hi, y))
    return remainder

def membership_index(revision):
    if revision is None:
        return {}, {}
    members = {record.source_id: record for record in revision.fluxes}
    if revision.flux_fragments is None:
        fragments = {sid: [(record.start, record.end)]
                     for sid, record in members.items()}
    else:
        fragments = {sid: [] for sid in members}
        for fragment in revision.flux_fragments:
            fragments[fragment.record.source_id].append((fragment.start, fragment.end))
    return members, {sid: sorted(spans) for sid, spans in fragments.items()}

def assemble_revision(revision_id, grid_id, parent_id, masses, members, fragments):
    fluxes = tuple(sorted(members.values(), key=lambda r: (r.logical_key(), r.source_id)))
    effective = tuple(sorted(
        (FluxFragment(members[sid], start, end)
         for sid, spans in fragments.items() if sid in members
         for start, end in spans),
        key=lambda f: (f.record.logical_key(), f.record.source_id, f.start, f.end)))
    return ObservationRevision(revision_id, grid_id, parent_id, tuple(masses),
                               fluxes, effective)

def build_observation_revision(grid, previous, masses, fluxes, sources):
    masses, fluxes = tuple(masses), tuple(fluxes)
    validate_mass_batch(grid, masses)
    validate_flux_batch(grid, fluxes)
    validate_source_bindings(masses + fluxes, sources)
    if previous is not None and previous.grid_id != grid.id:
        raise ValueError("base revision belongs to another grid")
    mass_map = {r.logical_key(): r for r in previous.masses} if previous else {}
    mass_map.update((r.logical_key(), r) for r in masses)
    members, fragments = membership_index(previous)
    members = dict(members)
    fragments = {sid: list(spans) for sid, spans in fragments.items()}
    for record in fluxes:
        key = record.logical_key()
        replaced = next((sid for sid, old in members.items()
                         if old.logical_key() == key and fragments.get(sid)), None)
        if replaced is not None:
            # A still-effective logical key hands exactly its remaining
            # fragments to the replacement record; other members are untouched.
            inherited = fragments.pop(replaced)
            del members[replaced]
            members[record.source_id] = record
            fragments[record.source_id] = inherited
        else:
            # Absent or fully hidden keys join as new full-interval keys.
            members[record.source_id] = record
            fragments[record.source_id] = [(record.start, record.end)]
    ordered_masses = tuple(mass_map[k] for k in sorted(mass_map))
    return assemble_revision(None, grid.id, previous.id if previous else None,
                             ordered_masses, members, fragments)

def build_flux_correction(grid, base, fluxes, sources):
    fluxes = tuple(fluxes)
    validate_flux_batch(grid, fluxes)
    validate_source_bindings(fluxes, sources)
    windows = defaultdict(list)
    for record in fluxes:
        windows[record.logical_key()[:3]].append(record)
    for face, records in windows.items():
        ordered = sorted(records, key=lambda r: (r.start, r.end, r.source_id))
        for earlier, later in zip(ordered, ordered[1:]):
            if later.start < earlier.end:
                raise ValueError("correction windows overlap on face " + str(face))
    members, fragments = membership_index(base)
    members = dict(members)
    fragments = {sid: list(spans) for sid, spans in fragments.items()}
    faces = defaultdict(set)
    for sid, record in members.items():
        faces[record.logical_key()[:3]].add(sid)
    for record in fluxes:
        face = record.logical_key()[:3]
        for sid in faces[face]:
            fragments[sid] = subtract_window(fragments.get(sid, []),
                                             record.start, record.end)
        members[record.source_id] = record
        faces[face].add(record.source_id)
        fragments[record.source_id] = [(record.start, record.end)]
    return assemble_revision(None, grid.id, base.id, base.masses, members, fragments)
