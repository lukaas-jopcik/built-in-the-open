"""Topological ordering for Skillcage step graphs."""


def topological_order(steps):
    """steps: list of dicts with 'id' and 'deps' (list of ids).

    Returns a list of step ids in an order that respects dependencies.
    Raises ValueError on unknown deps or cycles.
    """
    ids = [s["id"] for s in steps]
    id_set = set(ids)
    if len(id_set) != len(ids):
        raise ValueError("duplicate step id in .sky file")

    deps_of = {}
    for s in steps:
        deps = s.get("deps", [])
        for d in deps:
            if d not in id_set:
                raise ValueError(f"step '{s['id']}' depends on unknown step '{d}'")
        deps_of[s["id"]] = list(deps)

    # Kahn's algorithm, but iterate steps in file order for determinism.
    in_degree = {i: len(deps_of[i]) for i in ids}
    dependents = {i: [] for i in ids}
    for i in ids:
        for d in deps_of[i]:
            dependents[d].append(i)

    ready = [i for i in ids if in_degree[i] == 0]
    order = []
    while ready:
        # stable: pick in original file order among ready set
        ready.sort(key=lambda i: ids.index(i))
        current = ready.pop(0)
        order.append(current)
        for nxt in dependents[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                ready.append(nxt)

    if len(order) != len(ids):
        remaining = id_set - set(order)
        raise ValueError(f"cycle detected among steps: {sorted(remaining)}")

    return order


def topological_waves(steps):
    """Same validation/ordering guarantees as topological_order, but groups
    steps into "waves": every step in wave N has all its deps satisfied by
    waves 0..N-1, and nothing in wave N depends on anything else in wave N --
    so everything in a wave is safe to run concurrently. This is what the
    parallel executor (run_sky_parallel) fans out per wave via a thread pool.

    Returns a list of lists of step ids. Raises ValueError on unknown deps or
    cycles (same conditions as topological_order).
    """
    ids = [s["id"] for s in steps]
    id_set = set(ids)
    if len(id_set) != len(ids):
        raise ValueError("duplicate step id in .sky file")

    deps_of = {}
    for s in steps:
        deps = s.get("deps", [])
        for d in deps:
            if d not in id_set:
                raise ValueError(f"step '{s['id']}' depends on unknown step '{d}'")
        deps_of[s["id"]] = list(deps)

    in_degree = {i: len(deps_of[i]) for i in ids}
    dependents = {i: [] for i in ids}
    for i in ids:
        for d in deps_of[i]:
            dependents[d].append(i)

    waves = []
    placed = 0
    remaining_ids = list(ids)
    while remaining_ids:
        wave = [i for i in remaining_ids if in_degree[i] == 0]
        if not wave:
            break
        waves.append(wave)
        placed += len(wave)
        wave_set = set(wave)
        remaining_ids = [i for i in remaining_ids if i not in wave_set]
        for i in wave:
            for nxt in dependents[i]:
                in_degree[nxt] -= 1

    if placed != len(ids):
        remaining = id_set - {i for wave in waves for i in wave}
        raise ValueError(f"cycle detected among steps: {sorted(remaining)}")

    return waves
