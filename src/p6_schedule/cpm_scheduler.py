"""
CPM Scheduler - Forward and backward pass for construction schedules.

Calculates ES/EF, LS/LF, total float, and critical path.
Uses 7-day work calendar (HPD=8).

Internal model: EF = ES + duration - 1 for tasks, EF = ES for milestones (display convention).
FS+N: ES_succ = EF_pred + N + 1 for Task successors, ES_succ = EF_pred + N for Milestone successors.
P6 rule: task→task and milestone→task add +1 day; task→milestone is same day.
"""
from collections import defaultdict
from datetime import date, timedelta


def schedule(
    tasks: dict,
    rels: list[tuple],
    project_start: str | date,
    milestones: dict[str, date] | None = None,
) -> dict:
    """
    Run CPM forward + backward pass.

    Args:
        tasks: {code: {task_name, task_type, duration_days,
                        wbs_path, constraint_type, constraint_date}}
        rels: [(succ_code, pred_code, rel_type, lag_days)]
        project_start: project start date
        milestones: {milestone_code: contract_date} for verification

    Returns:
        {code: {es, ef, ls, lf, duration, task_name, task_type,
                total_float, is_critical, display_start, display_end}}
    """
    if isinstance(project_start, str):
        project_start = date.fromisoformat(project_start)

    codes = set(tasks.keys())

    preds_of: dict[str, list[tuple]] = defaultdict(list)
    succs_of: dict[str, list[tuple]] = defaultdict(list)
    for succ, pred, rel_type, lag in rels:
        preds_of[succ].append((pred, rel_type, lag))
        succs_of[pred].append((succ, rel_type, lag))

    topo = _topological_sort(codes, succs_of)

    # Forward pass
    es: dict[str, date] = {}
    ef: dict[str, date] = {}
    dur: dict[str, int] = {}

    for code in topo:
        t = tasks[code]
        d = 0 if t['task_type'] == 'Milestone' else t['duration_days']
        dur[code] = d

        pred_dates = []
        is_milestone = t['task_type'] == 'Milestone'
        for pred_code, rel_type, lag in preds_of[code]:
            pred_dates.append(_succ_start(es[pred_code], ef[pred_code], dur[pred_code],
                                          rel_type, lag, d, is_milestone))

        if pred_dates:
            calculated_es = max(pred_dates)
        else:
            calculated_es = project_start

        if t.get('constraint_type') == 'CS_MSO' and t.get('constraint_date'):
            calculated_es = date.fromisoformat(t['constraint_date'])

        es[code] = calculated_es
        ef[code] = calculated_es + timedelta(days=max(d - 1, 0))

    # Backward pass
    ls: dict[str, date] = {}
    lf: dict[str, date] = {}

    for code in reversed(topo):
        d = dur[code]
        succ_constraints = []

        for succ_code, rel_type, lag in succs_of[code]:
            succ_constraints.append(
                _pred_latest(ls[succ_code], lf[succ_code], dur[succ_code],
                             rel_type, lag, d)
            )

        if succ_constraints:
            latest_start = min(succ_constraints)
        else:
            latest_start = es[code]

        ls[code] = latest_start
        lf[code] = latest_start + timedelta(days=max(d - 1, 0))

    # Build results
    result: dict[str, dict] = {}
    for code in topo:
        t = tasks[code]
        d = dur[code]
        total_float = (ls[code] - es[code]).days
        is_crit = total_float <= 0

        result[code] = {
            'task_name': t['task_name'],
            'task_type': t['task_type'],
            'duration': d,
            'es': es[code],
            'ef': ef[code],
            'ls': ls[code],
            'lf': lf[code],
            'display_start': es[code],
            'display_end': ef[code],
            'total_float': total_float,
            'is_critical': is_crit,
        }

    # Critical path tracing
    critical_path = _trace_critical_path(result, succs_of)

    # Milestone verification
    milestone_check = None
    if milestones:
        milestone_check = {}
        for code, contract_date in milestones.items():
            if code in result:
                actual = result[code]['display_start']
                diff = (actual - contract_date).days
                milestone_check[code] = {
                    'actual': actual,
                    'contract': contract_date,
                    'diff': diff,
                    'status': '✅' if diff <= 0 else '❌',
                }

    return {
        'tasks': result,
        'critical_path': critical_path,
        'milestone_check': milestone_check,
        'project_start': project_start,
        'project_end': max(r['display_end'] for r in result.values()),
    }


def _topological_sort(codes: set, succs_of: dict) -> list[str]:
    in_deg: dict[str, int] = defaultdict(int)
    for c in codes:
        in_deg[c] = 0
    for pred, succs in succs_of.items():
        for succ, _, _ in succs:
            in_deg[succ] += 1

    queue = [c for c in codes if in_deg[c] == 0]
    topo: list[str] = []
    while queue:
        n = queue.pop(0)
        topo.append(n)
        for s, _, _ in succs_of[n]:
            in_deg[s] -= 1
            if in_deg[s] == 0:
                queue.append(s)
    return topo


def _succ_start(
    pred_es: date, pred_ef: date, pred_dur: int,
    rel_type: str, lag: int, succ_dur: int,
    succ_is_milestone: bool = False,
) -> date:
    """Calculate successor ES from one predecessor relationship.

    P6 rule: milestone→task adds +1 day for FS and SS.
    Milestone→milestone does not add +1.
    Task→task also adds +1 for FS (EF already accounts for duration).
    """
    if rel_type == 'FS':
        offset = 0 if succ_is_milestone else 1
        return pred_ef + timedelta(days=lag + offset)
    elif rel_type == 'SS':
        pred_is_ms = pred_dur == 0
        offset = 1 if (pred_is_ms and not succ_is_milestone) else 0
        return pred_es + timedelta(days=lag + offset)
    elif rel_type == 'FF':
        succ_ef = pred_ef + timedelta(days=lag)
        return succ_ef - timedelta(days=max(succ_dur - 1, 0))
    elif rel_type == 'SF':
        succ_ef = pred_es + timedelta(days=lag)
        return succ_ef - timedelta(days=max(succ_dur - 1, 0))
    return pred_es


def _pred_latest(
    succ_ls: date, succ_lf: date, succ_dur: int,
    rel_type: str, lag: int, pred_dur: int,
) -> date:
    """Calculate predecessor LS from one successor relationship."""
    if rel_type == 'FS':
        succ_is_ms = succ_dur == 0
        offset = 0 if succ_is_ms else 1
        pred_lf = succ_ls - timedelta(days=lag + offset)
        return pred_lf - timedelta(days=max(pred_dur - 1, 0))
    elif rel_type == 'SS':
        pred_is_ms = pred_dur == 0
        succ_is_ms = succ_dur == 0
        offset = 1 if (pred_is_ms and not succ_is_ms) else 0
        return succ_ls - timedelta(days=lag + offset)
    elif rel_type == 'FF':
        pred_lf = succ_lf - timedelta(days=lag)
        return pred_lf - timedelta(days=max(pred_dur - 1, 0))
    elif rel_type == 'SF':
        return succ_lf - timedelta(days=lag)
    return succ_ls


def _trace_critical_path(result: dict, succs_of: dict) -> list[list[str]]:
    """Trace all critical paths through the network."""
    crit_tasks = {c for c, r in result.items() if r['is_critical']}
    if not crit_tasks:
        return []

    crit_succs: dict[str, list[str]] = defaultdict(list)
    crit_preds: dict[str, list[str]] = defaultdict(list)
    for pred, succs in succs_of.items():
        for succ, _, _ in succs:
            if pred in crit_tasks and succ in crit_tasks:
                crit_succs[pred].append(succ)
                crit_preds[succ].append(pred)

    starts = [c for c in crit_tasks if not crit_preds[c]]
    if not starts:
        starts = [min(crit_tasks, key=lambda c: result[c]['es'])]

    paths: list[list[str]] = []
    stack = [(s, [s]) for s in starts]
    while stack:
        node, path = stack.pop()
        nexts = [n for n in crit_succs[node] if n not in path]
        if not nexts:
            paths.append(path)
        for n in nexts:
            stack.append((n, path + [n]))

    return paths


def print_schedule(result: dict) -> None:
    """Print schedule results in table format."""
    tasks = result['tasks']

    print(f'{"Code":<12} {"Name":<22} {"Type":<4} {"Dur":>4} '
          f'{"Start":<12} {"End":<12} {"LS":<12} {"LF":<12} '
          f'{"Float":>5} {"Crit":>4}')
    print('=' * 120)

    for code, t in sorted(tasks.items(), key=lambda x: x[1]['es']):
        ttype = 'MS' if t['task_type'] == 'Milestone' else 'Task'
        crit = '***' if t['is_critical'] else ''
        print(f'{code:<12} {t["task_name"]:<22} {ttype:<4} {t["duration"]:>4} '
              f'{t["display_start"]!s:<12} {t["display_end"]!s:<12} '
              f'{t["ls"]!s:<12} {t["lf"]!s:<12} '
              f'{t["total_float"]:>5}d {crit:>4}')

    crit_count = sum(1 for t in tasks.values() if t['is_critical'])
    print(f'\nTotal: {len(tasks)} tasks, {crit_count} critical')
    print(f'Project: {result["project_start"]} ~ {result["project_end"]}')


def print_critical_paths(result: dict) -> None:
    """Print critical path analysis."""
    paths = result['critical_path']
    tasks = result['tasks']

    if not paths:
        print('No critical path found.')
        return

    print(f'Critical paths: {len(paths)}')
    for i, path in enumerate(paths, 1):
        print(f'\nCritical Path {i} ({len(path)} tasks):')
        for code in path:
            t = tasks[code]
            print(f'  {code:<12} {t["task_name"]:<22} '
                  f'{t["display_start"]} ~ {t["display_end"]}  '
                  f'dur={t["duration"]}d  float={t["total_float"]}d')


def print_milestone_check(result: dict) -> None:
    """Print milestone verification against contract dates."""
    check = result.get('milestone_check')
    if not check:
        print('No milestone verification data.')
        return

    tasks = result['tasks']
    print(f'{"Code":<12} {"Name":<22} {"Actual":<12} {"Contract":<12} {"Diff":>5} {"Status":>4}')
    print('=' * 80)

    all_pass = True
    for code, m in sorted(check.items(), key=lambda x: x[1]['actual']):
        name = tasks[code]['task_name'] if code in tasks else code
        diff_str = f'{m["diff"]:>+d}' if m["diff"] != 0 else '  ='
        print(f'{code:<12} {name:<22} {m["actual"]!s:<12} {m["contract"]!s:<12} {diff_str:>5} {m["status"]:>4}')
        if m["diff"] > 0:
            all_pass = False

    if all_pass:
        print('\n✅ All milestones meet contract requirements!')
    else:
        print('\n❌ Some milestones exceed contract dates!')
