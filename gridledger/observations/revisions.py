from gridledger.observations.model import ObservationRevision
from gridledger.observations.masses import validate_mass_batch
from gridledger.observations.fluxes import validate_flux_batch

def validate_source_bindings(records, existing):
    bindings = dict(existing)
    for record in records:
        if record.source_id in bindings and bindings[record.source_id] != record:
            raise ValueError("source identity cannot be redefined: " + record.source_id)
        bindings[record.source_id] = record

def build_observation_revision(grid, previous, masses, fluxes, sources):
    masses, fluxes = tuple(masses), tuple(fluxes)
    validate_mass_batch(grid, masses)
    validate_flux_batch(grid, fluxes)
    validate_source_bindings(masses + fluxes, sources)
    if previous is not None and previous.grid_id != grid.id:
        raise ValueError("base revision belongs to another grid")
    mass_map = {r.logical_key(): r for r in previous.masses} if previous else {}
    flux_map = {r.logical_key(): r for r in previous.fluxes} if previous else {}
    mass_map.update((r.logical_key(), r) for r in masses)
    flux_map.update((r.logical_key(), r) for r in fluxes)
    return ObservationRevision(None, grid.id, previous.id if previous else None,
                               tuple(mass_map[k] for k in sorted(mass_map)),
                               tuple(flux_map[k] for k in sorted(flux_map)))
