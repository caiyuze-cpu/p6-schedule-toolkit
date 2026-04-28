"""
P6 SQLite database result reader (read-only).

Reads schedule results from P6's SQLite database, including dates,
critical path, and total float. Never writes to the database.

Usage:
    python -m p6_schedule.read_results --project "Project Name"
"""
import sqlite3
from collections import defaultdict
from datetime import datetime


DEFAULT_DB = 'PPMDBSQLite.db'


def connect_db(db_path: str) -> sqlite3.Connection:
    db_path = db_path.replace('\\', '/')
    conn = sqlite3.connect(f'file:///{db_path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def to_dicts(rows: list) -> list[dict]:
    return [{k.lower(): v for k, v in dict(r).items()} for r in rows]


def to_dict(row) -> dict | None:
    if row is None:
        return None
    return {k.lower(): v for k, v in dict(row).items()}


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT proj_id, proj_short_name, plan_start_date, plan_end_date "
        "FROM PROJECT WHERE delete_session_id IS NULL "
        "ORDER BY proj_id"
    ).fetchall()
    return to_dicts(rows)


def get_project(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT proj_id, proj_short_name, plan_start_date, plan_end_date "
        "FROM PROJECT WHERE proj_short_name LIKE ? AND delete_session_id IS NULL",
        (f'%{name}%',)
    ).fetchone()
    return to_dict(row)


def get_tasks(conn: sqlite3.Connection, proj_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT t.task_id, t.task_code, t.task_name, t.task_type, "
        "  t.target_drtn_hr_cnt, t.remain_drtn_hr_cnt, "
        "  t.early_start_date, t.early_end_date, "
        "  t.late_start_date, t.late_end_date, "
        "  t.act_start_date, t.act_end_date, "
        "  t.status_code, t.total_float_hr_cnt, "
        "  w.wbs_short_name "
        "FROM TASK t "
        "JOIN PROJWBS w ON t.wbs_id = w.wbs_id "
        "WHERE t.proj_id = ? AND t.delete_session_id IS NULL "
        "ORDER BY t.early_start_date, t.task_code",
        (proj_id,)
    ).fetchall()
    return to_dicts(rows)


def get_relationships(conn: sqlite3.Connection, proj_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT tp.task_pred_id, "
        "  tsucc.task_code AS succ_code, tsucc.task_name AS succ_name, "
        "  tpred.task_code AS pred_code, tpred.task_name AS pred_name, "
        "  tp.pred_type, tp.lag_hr_cnt "
        "FROM TASKPRED tp "
        "JOIN TASK tsucc ON tp.task_id = tsucc.task_id "
        "JOIN TASK tpred ON tp.pred_task_id = tpred.task_id "
        "WHERE tp.proj_id = ? AND tp.delete_session_id IS NULL "
        "ORDER BY tp.task_pred_id",
        (proj_id,)
    ).fetchall()
    return to_dicts(rows)


def fmt_date(val: str | None) -> str:
    if not val:
        return '-'
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(val, fmt).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            continue
    return val[:10] if len(val) >= 10 else val


def fmt_hours(hours: int | None) -> str:
    if hours is None:
        return '-'
    return f'{hours // 8}d'


def is_critical(t: dict) -> bool:
    f = t.get('total_float_hr_cnt')
    return f is not None and f <= 0


def print_projects(projects: list[dict]) -> None:
    if not projects:
        print('No projects found.')
        return
    print(f'{len(projects)} project(s):')
    print(f'{"ID":>6}  {"Name":<30}  {"Start":<12}  {"End":<12}')
    print('-' * 70)
    for p in projects:
        print(f'{p["proj_id"]:>6}  {p["proj_short_name"]:<30}  '
              f'{fmt_date(p["plan_start_date"]):<12}  {fmt_date(p["plan_end_date"]):<12}')


def print_task_table(
    tasks: list[dict],
    show_critical_only: bool = False,
    show_milestones_only: bool = False,
) -> None:
    filtered = tasks
    if show_critical_only:
        filtered = [t for t in tasks if is_critical(t)]
    if show_milestones_only:
        filtered = [t for t in tasks if t['task_type'] in ('TT_Mile', 'TT_FinMile', 'TT_StartMile')]

    if not filtered:
        print('No matching tasks.')
        return

    print(f'{"Code":<16} {"Name":<24} {"Type":<6} {"Dur":>5} '
          f'{"ES":<12} {"EF":<12} {"LS":<12} {"LF":<12} '
          f'{"Float":>5} {"Crit":>4}  WBS')
    print('=' * 150)

    for t in filtered:
        ttype = 'MS' if t['task_type'] in ('TT_Mile', 'TT_FinMile', 'TT_StartMile') else 'Task'
        dur = fmt_hours(t['remain_drtn_hr_cnt'])
        flt = fmt_hours(t['total_float_hr_cnt'])
        crit_mark = '***' if is_critical(t) else ''

        print(f'{t["task_code"]:<16} {t["task_name"]:<24} {ttype:<6} {dur:>5} '
              f'{fmt_date(t["early_start_date"]):<12} {fmt_date(t["early_end_date"]):<12} '
              f'{fmt_date(t["late_start_date"]):<12} {fmt_date(t["late_end_date"]):<12} '
              f'{flt:>5} {crit_mark:>4}  {t["wbs_short_name"]}')

    if show_critical_only:
        print(f'\nCritical tasks: {len(filtered)}')
    elif show_milestones_only:
        print(f'\nMilestones: {len(filtered)}')
    else:
        crit_count = sum(1 for t in filtered if is_critical(t))
        print(f'\nTotal tasks: {len(filtered)}, critical: {crit_count}')


def print_gantt(tasks: list[dict]) -> None:
    if not tasks:
        print('No task data.')
        return

    starts = [t['early_start_date'][:10] for t in tasks if t.get('early_start_date')]
    ends = [t['early_end_date'][:10] for t in tasks if t.get('early_end_date')]

    if not starts or not ends:
        print('No date data. Schedule in P6 first (F9).')
        return

    min_date = min(starts)
    max_date = max(ends)

    try:
        min_d = datetime.strptime(min_date, '%Y-%m-%d')
        max_d = datetime.strptime(max_date, '%Y-%m-%d')
    except ValueError:
        print(f'Date format error: {min_date} ~ {max_date}')
        return

    total_days = (max_d - min_d).days
    bar_width = 80

    print(f'Project range: {min_date} ~ {max_date} ({total_days} days)\n')

    for t in tasks:
        es = t['early_start_date']
        ee = t['early_end_date']
        if not es or not ee:
            continue

        try:
            es_d = datetime.strptime(es[:10], '%Y-%m-%d')
            ee_d = datetime.strptime(ee[:10], '%Y-%m-%d')
        except ValueError:
            continue

        start_offset = (es_d - min_d).days
        duration = max((ee_d - es_d).days, 1)

        bar_start = int(start_offset / max(total_days, 1) * bar_width)
        bar_len = max(int(duration / max(total_days, 1) * bar_width), 1)

        bar = ' ' * bar_start + '#' * bar_len
        marker = '*' if is_critical(t) else ' '

        label = t['task_code'][:14]
        print(f'{marker}{label:<15} |{bar:<{bar_width}}| {fmt_date(es)} ~ {fmt_date(ee)}')


def print_critical_path(tasks: list[dict], rels: list[dict]) -> None:
    crit_tasks = {t['task_code']: t for t in tasks if is_critical(t)}
    if not crit_tasks:
        print('No critical tasks found. Schedule in P6 first (F9).')
        return

    succ_of: dict[str, list[str]] = defaultdict(list)
    pred_of: dict[str, list[str]] = defaultdict(list)
    for r in rels:
        if r['pred_code'] in crit_tasks and r['succ_code'] in crit_tasks:
            succ_of[r['pred_code']].append(r['succ_code'])
            pred_of[r['succ_code']].append(r['pred_code'])

    starts = [c for c in crit_tasks if not pred_of[c]]
    if not starts:
        starts = [list(crit_tasks.keys())[0]]

    paths: list[list[str]] = []
    stack = [(s, [s]) for s in starts]
    while stack:
        node, path = stack.pop()
        nexts = succ_of[node]
        if not nexts:
            paths.append(path)
        for n in nexts:
            if n not in path:
                stack.append((n, path + [n]))

    print(f'Critical tasks: {len(crit_tasks)}')
    print(f'Critical paths: {len(paths)}')
    print()

    for i, path in enumerate(paths, 1):
        print(f'Critical Path {i} ({len(path)} tasks):')
        for code in path:
            t = crit_tasks[code]
            dur = fmt_hours(t['remain_drtn_hr_cnt'])
            print(f'  {code:<16} {t["task_name"]:<24} '
                  f'{fmt_date(t["early_start_date"])} ~ {fmt_date(t["early_end_date"])}  '
                  f'dur={dur}')
        print()


def print_relationships(rels: list[dict]) -> None:
    if not rels:
        print('No relationships.')
        return

    print(f'{len(rels)} relationships:')
    print(f'{"Pred":<16} {"→":>2} {"Succ":<16} {"Type":>4} {"Lag":>6}')
    print('-' * 60)
    for r in rels:
        pt = r['pred_type'].replace('PR_', '') if r['pred_type'] else '?'
        lag = fmt_hours(r['lag_hr_cnt'])
        print(f'{r["pred_code"]:<16} → {r["succ_code"]:<16} {pt:>4} {lag:>6}')
