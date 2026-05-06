"""
DCMA 14-Point Schedule Quality Evaluation for construction schedules.

Implements the Defense Contract Management Agency's 14-point schedule quality
checklist for Primavera P6 schedules. Used to validate schedule modeling quality
before P6 import.

Reference:
    DCMA 14-Point Schedule Quality Evaluation
    https://www.dcma.mil/Scheduling/Schedule-Quality-Plan/

Usage:
    from p6_schedule.dcma_checker import dcma_check, print_dcma_report
    result = dcma_check(tasks, rels, project_start='2026-01-01')
    print_dcma_report(result)
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .cpm_scheduler import schedule as cpm_schedule


@dataclass
class DCMAIssue:
    check_number: int
    check_name: str
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    task_code: str | None
    message: str


@dataclass
class DCMAResult:
    passed: bool
    total_issues: int
    error_count: int
    warning_count: int
    info_count: int
    issues: list[DCMAIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# Threshold constants (customizable per project type)
THRESHOLDS = {
    'max_lag_days': 30,          # Check 3: unreasonably large lags
    'max_task_duration': 60,     # Check 10: very long tasks
    'max_long_path': 500,        # Check 12: single chain length
    'low_float_threshold': 5,   # Check 7: low float warning
    'high_float_threshold': 60,  # Check 8: high float warning
    'max_constraint_ratio': 0.3, # Check 4: >30% tasks with constraints
}


def dcma_check(
    tasks: dict,
    rels: list[tuple],
    project_start: str | date,
    thresholds: dict | None = None,
) -> DCMAResult:
    """
    Run DCMA 14-Point Schedule Quality Evaluation.

    Args:
        tasks: {code: {task_name, task_type, duration_days, constraint_type, ...}}
        rels: [(succ_code, pred_code, rel_type, lag_days)]
        project_start: project start date
        thresholds: optional custom thresholds override

    Returns:
        DCMAResult with issues and statistics
    """
    if isinstance(project_start, str):
        project_start_date = date.fromisoformat(project_start)
    else:
        project_start_date = project_start

    t = {**THRESHOLDS, **(thresholds or {})}
    issues: list[DCMAIssue] = []
    stats: dict = {}

    # Run CPM to get float values
    cpm_result = cpm_schedule(tasks, rels, project_start)
    task_results = cpm_result['tasks']

    # Build predecessor/successor maps
    preds_of: dict[str, list[tuple]] = defaultdict(list)
    succs_of: dict[str, list[tuple]] = defaultdict(list)
    for succ, pred, rtype, lag in rels:
        preds_of[succ].append((pred, rtype, lag))
        succs_of[pred].append((succ, rtype, lag))

    # =================================================================
    # Check 1: Logic - Network completeness
    # =================================================================
    _check_1_logic(tasks, rels, preds_of, succs_of, issues)

    # =================================================================
    # Check 2: Leads - Negative lags
    # =================================================================
    _check_2_leads(rels, issues)

    # =================================================================
    # Check 3: Lags - Unreasonably large lags
    # =================================================================
    _check_3_lags(rels, t['max_lag_days'], issues)

    # =================================================================
    # Check 4: Constraints - Too many constraints
    # =================================================================
    _check_4_constraints(tasks, t['max_constraint_ratio'], issues)

    # =================================================================
    # Check 5: Relationship Types - Only FS (lack of variety)
    # =================================================================
    _check_5_relationship_types(rels, issues)

    # =================================================================
    # Check 6: Hard Constraints - MFEO/MFIN usage
    # =================================================================
    _check_6_hard_constraints(tasks, issues)

    # =================================================================
    # Check 7: Low Float - High risk areas
    # =================================================================
    _check_7_low_float(task_results, t['low_float_threshold'], issues)

    # =================================================================
    # Check 8: High Float - May indicate missing logic
    # =================================================================
    _check_8_high_float(task_results, t['high_float_threshold'], issues)

    # =================================================================
    # Check 9: Invalid Dates - Weekends/holidays
    # =================================================================
    _check_9_invalid_dates(task_results, issues)

    # =================================================================
    # Check 10: CM Tasks - Very long duration tasks
    # =================================================================
    _check_10_long_tasks(tasks, t['max_task_duration'], issues)

    # =================================================================
    # Check 11: Missing Constraints - Critical path milestones need constraints
    # =================================================================
    _check_11_missing_constraints(tasks, task_results, issues)

    # =================================================================
    # Check 12: Long Paths - Single chain > N tasks
    # =================================================================
    _check_12_long_paths(succs_of, tasks, t['max_long_path'], issues)

    # =================================================================
    # Check 13: High Tenacity - Tightly coupled chains
    # =================================================================
    _check_13_high_tenacity(preds_of, succs_of, tasks, issues)

    # =================================================================
    # Check 14: Zero or Negative Total Float - Critical path tasks
    # =================================================================
    _check_14_zero_float(task_results, issues)

    # Compute statistics
    stats = {
        'total_tasks': len(tasks),
        'total_relationships': len(rels),
        'critical_tasks': sum(1 for r in task_results.values() if r['is_critical']),
        'milestones': sum(1 for t in tasks.values() if t['task_type'] == 'Milestone'),
        'tasks_with_constraints': sum(1 for t in tasks.values() if t.get('constraint_type')),
        'avg_duration': sum(t.get('duration_days', 0) for t in tasks.values()) / len(tasks) if tasks else 0,
        'project_start': project_start_date,
        'project_end': cpm_result['project_end'],
    }

    error_count = sum(1 for i in issues if i.severity == 'ERROR')
    warning_count = sum(1 for i in issues if i.severity == 'WARNING')
    info_count = sum(1 for i in issues if i.severity == 'INFO')

    return DCMAResult(
        passed=error_count == 0,
        total_issues=len(issues),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        issues=issues,
        stats=stats,
    )


def _check_1_logic(tasks, rels, preds_of, succs_of, issues):
    """Check 1: Network logic completeness."""
    codes = set(tasks.keys())

    # Check for orphaned tasks (no predecessors AND no successors)
    for code in codes:
        has_pred = code in preds_of and preds_of[code]
        has_succ = code in succs_of and succs_of[code]
        if not has_pred and not has_succ:
            issues.append(DCMAIssue(
                check_number=1,
                check_name='Logic',
                severity='ERROR',
                task_code=code,
                message=f'Task {code} is orphaned (no predecessors and no successors)',
            ))

    # Check for tasks referenced but not defined
    for succ, pred, _, _ in rels:
        if pred not in codes:
            issues.append(DCMAIssue(
                check_number=1,
                check_name='Logic',
                severity='ERROR',
                task_code=succ,
                message=f'Predecessor {pred} referenced but not defined (by {succ})',
            ))


def _check_2_leads(rels, issues):
    """Check 2: Negative lags (leads)."""
    for succ, pred, rtype, lag in rels:
        if lag < 0:
            issues.append(DCMAIssue(
                check_number=2,
                check_name='Leads',
                severity='ERROR',
                task_code=succ,
                message=f'Negative lag ({lag} days) found in relationship {pred} → {succ}',
            ))


def _check_3_lags(rels, max_lag, issues):
    """Check 3: Unreasonably large lags."""
    for succ, pred, rtype, lag in rels:
        if abs(lag) > max_lag:
            issues.append(DCMAIssue(
                check_number=3,
                check_name='Lags',
                severity='WARNING',
                task_code=succ,
                message=f'Large lag ({lag} days) in {pred} → {succ} exceeds {max_lag} day threshold',
            ))


def _check_4_constraints(tasks, max_ratio, issues):
    """Check 4: Too many constraints."""
    tasks_with_constraints = sum(1 for t in tasks.values() if t.get('constraint_type'))
    total = len(tasks)
    if total == 0:
        return

    ratio = tasks_with_constraints / total
    if ratio > max_ratio:
        issues.append(DCMAIssue(
            check_number=4,
            check_name='Constraints',
            severity='WARNING',
            task_code=None,
            message=f'{tasks_with_constraints}/{total} tasks ({ratio:.1%}) have constraints, exceeds {max_ratio:.0%} threshold',
        ))


def _check_5_relationship_types(rels, issues):
    """Check 5: Relationship type variety (only FS is suspicious)."""
    rel_types = set(rtype for _, _, rtype, _ in rels)

    if len(rels) > 5 and rel_types == {'FS'}:
        issues.append(DCMAIssue(
            check_number=5,
            check_name='Relationship Types',
            severity='WARNING',
            task_code=None,
            message=f'All {len(rels)} relationships are FS type - schedule may be over-constrained',
        ))


def _check_6_hard_constraints(tasks, issues):
    """Check 6: Hard constraints (MFEO/MFIN) usage."""
    hard_constraints = {'CS_MFEO', 'CS_MFIN', 'CS_MSO'}
    for code, t in tasks.items():
        cstr = t.get('constraint_type', '')
        if cstr in hard_constraints and cstr != 'CS_MSO':
            issues.append(DCMAIssue(
                check_number=6,
                check_name='Hard Constraints',
                severity='WARNING',
                task_code=code,
                message=f'Hard constraint {cstr} used on task {code} - P6 may ignore this constraint type',
            ))


def _check_7_low_float(task_results, threshold, issues):
    """Check 7: Low float areas (high risk)."""
    for code, r in task_results.items():
        if 0 < r['total_float'] <= threshold:
            issues.append(DCMAIssue(
                check_number=7,
                check_name='Low Float',
                severity='WARNING',
                task_code=code,
                message=f'Task {code} has only {r["total_float"]} days float (≤ {threshold})',
            ))


def _check_8_high_float(task_results, threshold, issues):
    """Check 8: Very high float (may indicate missing logic)."""
    for code, r in task_results.items():
        if r['total_float'] > threshold:
            issues.append(DCMAIssue(
                check_number=8,
                check_name='High Float',
                severity='INFO',
                task_code=code,
                message=f'Task {code} has {r["total_float"]} days float (> {threshold}) - review for missing logic',
            ))


def _check_9_invalid_dates(task_results, issues):
    """Check 9: Tasks scheduled on weekends (invalid work calendar)."""
    for code, r in task_results.items():
        start = r['es']
        # Saturday = 5, Sunday = 6
        if start.weekday() >= 5:
            issues.append(DCMAIssue(
                check_number=9,
                check_name='Invalid Dates',
                severity='WARNING',
                task_code=code,
                message=f'Task {code} starts on {start.strftime("%Y-%m-%d (%A)")} - weekend date',
            ))


def _check_10_long_tasks(tasks, threshold, issues):
    """Check 10: Very long duration tasks."""
    for code, t in tasks.items():
        if t['task_type'] != 'Milestone':
            d = t.get('duration_days', 0)
            if d > threshold:
                issues.append(DCMAIssue(
                    check_number=10,
                    check_name='Long Duration Tasks',
                    severity='INFO',
                    task_code=code,
                    message=f'Task {code} has {d} days duration (> {threshold}) - consider splitting',
                ))


def _check_11_missing_constraints(tasks, task_results, issues):
    """Check 11: Critical milestones should have constraints."""
    for code, r in task_results.items():
        if r['task_type'] == 'Milestone' and r['is_critical']:
            t = tasks.get(code, {})
            if not t.get('constraint_type'):
                issues.append(DCMAIssue(
                    check_number=11,
                    check_name='Missing Constraints',
                    severity='WARNING',
                    task_code=code,
                    message=f'Critical milestone {code} has no constraint - add CS_MSO constraint',
                ))


def _check_12_long_paths(succs_of, tasks, threshold, issues):
    """Check 12: Single chain longer than threshold."""
    codes = set(tasks.keys())
    visited: set = set()

    for start_code in codes:
        if start_code in visited:
            continue

        # Find longest path starting from this node
        path: list = []
        current = start_code
        while current in succs_of and succs_of[current]:
            if len(path) > threshold:
                issues.append(DCMAIssue(
                    check_number=12,
                    check_name='Long Paths',
                    severity='WARNING',
                    task_code=current,
                    message=f'Linear chain exceeds {threshold} tasks - add parallel activities',
                ))
                break

            next_tasks = [s for s, _, _ in succs_of[current] if s not in path]
            if not next_tasks:
                break
            # Follow the longest next chain
            current = max(next_tasks, key=lambda x: _count_succs(x, succs_of, set()))
            path.append(current)
            visited.add(current)

    # Also check backward longest path
    visited.clear()
    preds_of_back: dict = defaultdict(list)
    for pred, succs in succs_of.items():
        for s, _, _ in succs:
            preds_of_back[s].append(pred)

    for start_code in codes:
        if start_code in visited:
            continue
        path_length = 0
        current = start_code
        while current in preds_of_back and preds_of_back[current]:
            next_tasks = [p for p in preds_of_back[current] if p != current]
            if not next_tasks:
                break
            current = next_tasks[0]
            path_length += 1
            if path_length > threshold:
                issues.append(DCMAIssue(
                    check_number=12,
                    check_name='Long Paths',
                    severity='WARNING',
                    task_code=current,
                    message=f'Backward chain exceeds {threshold} tasks - add parallel activities',
                ))
                break


def _count_succs(code, succs_of, visited):
    """Helper: count successors in chain."""
    if code in visited or code not in succs_of:
        return 0
    visited.add(code)
    return 1 + max((_count_succs(s, succs_of, visited) for s, _, _ in succs_of[code]), default=0)


def _check_13_high_tenacity(preds_of, succs_of, tasks, issues):
    """Check 13: High tenacity - tightly coupled task chains."""
    # Tasks with many predecessors AND many successors (complex coupling)
    for code in tasks:
        num_preds = len(preds_of.get(code, []))
        num_succs = len(succs_of.get(code, []))
        # High tenacity: >3 preds AND >3 succs
        if num_preds > 3 and num_succs > 3:
            issues.append(DCMAIssue(
                check_number=13,
                check_name='High Tenacity',
                severity='INFO',
                task_code=code,
                message=f'Task {code} has {num_preds} predecessors and {num_succs} successors - review for complexity',
            ))


def _check_14_zero_float(task_results, issues):
    """Check 14: Zero or negative float (critical path tasks)."""
    for code, r in task_results.items():
        if r['total_float'] <= 0:
            issues.append(DCMAIssue(
                check_number=14,
                check_name='Zero/Negative Float',
                severity='INFO',
                task_code=code,
                message=f'Task {code} is on critical path (float={r["total_float"]} days)',
            ))


def print_dcma_report(result: DCMAResult) -> None:
    """Print DCMA 14-point evaluation report."""
    print('=' * 70)
    print('DCMA 14-Point Schedule Quality Evaluation')
    print('=' * 70)

    # Summary
    print(f'\nResult: {"✅ PASSED" if result.passed else "❌ FAILED"}')
    print(f'Issues: {result.error_count} errors, {result.warning_count} warnings, {result.info_count} info')

    # Statistics
    s = result.stats
    print(f'\n--- Schedule Statistics ---')
    print(f'Total Tasks:      {s.get("total_tasks", 0):>6}')
    print(f'Total Relations: {s.get("total_relationships", 0):>6}')
    print(f'Critical Tasks:  {s.get("critical_tasks", 0):>6}')
    print(f'Milestones:      {s.get("milestones", 0):>6}')
    print(f'With Constraints:{s.get("tasks_with_constraints", 0):>6}')
    print(f'Avg Duration:    {s.get("avg_duration", 0):>6.1f} days')
    print(f'Project Start:   {s.get("project_start", "N/A")}')
    print(f'Project End:     {s.get("project_end", "N/A")}')

    # Issues by check
    if result.issues:
        print(f'\n--- Issues by DCMA Point ---')
        current_check = 0
        for issue in sorted(result.issues, key=lambda x: (x.check_number, x.severity)):
            if issue.check_number != current_check:
                print(f'\n[{issue.check_number}] {issue.check_name}:')
                current_check = issue.check_number

            severity_marker = {
                'ERROR': '🔴',
                'WARNING': '🟡',
                'INFO': '🔵',
            }.get(issue.severity, '•')

            task_str = f' [{issue.task_code}]' if issue.task_code else ''
            print(f'  {severity_marker} {issue.severity}:{task_str} {issue.message}')

    # DCMA Point Status
    print(f'\n--- DCMA 14-Point Status ---')
    check_status: dict[int, str] = {}
    for issue in result.issues:
        if issue.check_number not in check_status:
            check_status[issue.check_number] = issue.severity
        elif issue.severity == 'ERROR':
            check_status[issue.check_number] = 'ERROR'
        elif issue.severity == 'WARNING' and check_status[issue.check_number] != 'ERROR':
            check_status[issue.check_number] = 'WARNING'

    dcma_names = {
        1: 'Logic',
        2: 'Leads',
        3: 'Lags',
        4: 'Constraints',
        5: 'Relationship Types',
        6: 'Hard Constraints',
        7: 'Low Float',
        8: 'High Float',
        9: 'Invalid Dates',
        10: 'Long Duration Tasks',
        11: 'Missing Constraints',
        12: 'Long Paths',
        13: 'High Tenacity',
        14: 'Zero/Negative Float',
    }

    for i in range(1, 15):
        status = check_status.get(i)
        if status == 'ERROR':
            print(f'  [{i:2d}] ❌ {dcma_names[i]:25s} - FAILED')
        elif status == 'WARNING':
            print(f'  [{i:2d}] 🟡 {dcma_names[i]:25s} - WARNING')
        elif status == 'INFO':
            print(f'  [{i:2d}] 🔵 {dcma_names[i]:25s} - INFO')
        else:
            print(f'  [{i:2d}] ✅ {dcma_names[i]:25s} - PASSED')

    print()
    print('=' * 70)
