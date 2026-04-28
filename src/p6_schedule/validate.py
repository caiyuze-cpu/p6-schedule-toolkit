"""
CPM network validation for construction schedules.

Validates task dependencies for:
- Missing predecessors
- Invalid relationship types
- Circular dependencies
- Network completeness (single entry/exit points)
"""
from collections import defaultdict


def validate_network(tasks: dict, rels: list[tuple]) -> None:
    codes = set(tasks.keys())

    for succ, pred, rtype, lag in rels:
        if pred not in codes:
            raise ValueError(f'Predecessor {pred} not found (referenced by {succ})')
        if rtype not in ('FS', 'SS', 'FF', 'SF'):
            raise ValueError(f'Invalid rel_type {rtype} ({pred}→{succ}), must be FS/SS/FF/SF')

    succs_of: dict[str, list[str]] = defaultdict(list)
    preds_of: dict[str, list[str]] = defaultdict(list)
    for succ, pred, rtype, lag in rels:
        succs_of[pred].append(succ)
        preds_of[succ].append(pred)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {c: WHITE for c in codes}

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for s in succs_of[node]:
            if color[s] == GRAY:
                cycle_start = path.index(s)
                cycle = path[cycle_start:]
                raise ValueError(f'Circular dependency: {" → ".join(cycle)} → {s}')
            if color[s] == WHITE:
                dfs(s, path)
        path.pop()
        color[node] = BLACK

    for c in codes:
        if color[c] == WHITE:
            dfs(c, [])

    starts = [c for c in codes if not preds_of[c]]
    ends = [c for c in codes if not succs_of[c]]

    if not starts:
        raise ValueError('Network has no start point (all tasks have predecessors)')
    if not ends:
        raise ValueError('Network has no end point (all tasks have successors)')

    if len(starts) > 1:
        print(f'[Warning] {len(starts)} start points found: {", ".join(starts)}')
        print(f'  Consider adding a "Project Start" milestone to merge all starts via FS+0')
    if len(ends) > 1:
        print(f'[Warning] {len(ends)} end points found: {", ".join(ends)}')
        print(f'  Consider adding a "Project Finish" milestone to merge all ends via FS+0')

    in_deg: dict[str, int] = defaultdict(int)
    for c in codes:
        in_deg[c] = 0
    for succ, pred, _, _ in rels:
        in_deg[succ] += 1

    queue = [c for c in codes if in_deg[c] == 0]
    topo: list[str] = []
    while queue:
        n = queue.pop(0)
        topo.append(n)
        for s in succs_of[n]:
            in_deg[s] -= 1
            if in_deg[s] == 0:
                queue.append(s)

    if len(topo) != len(codes):
        raise ValueError(f'Topological sort incomplete ({len(topo)}/{len(codes)}), unreachable tasks exist')

    print(f'Network validation passed: {len(codes)} tasks, {len(rels)} relationships')
    print(f'  Start points: {", ".join(starts)}')
    print(f'  End points: {", ".join(ends)}')
