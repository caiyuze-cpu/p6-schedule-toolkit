"""
CSV to XER converter for Primavera P6.

Converts a CSV construction schedule into a P6-importable XER file.
Only writes durations (not fixed dates) - P6's scheduler calculates all dates.

Usage:
    python -m p6_schedule.csv_to_xer input.csv output.xer --project "Project Name"
"""
import csv
from collections import defaultdict
from datetime import datetime

from .validate import validate_network


HPD = 8
ID_OFFSET = {
    'calendar': 9001,
    'project': 9900,
    'wbs': 91001,
    'task': 920001,
    'taskpred': 9300001,
}

CLNDR_DATA = (
    '(0||CalendarData()(    (0||DaysOfWeek()('
    + ''.join(
        f'      (0||{d}()(        (0||0(s|08:00|f|12:00)())        (0||1(s|13:00|f|17:00)())))'
        for d in range(1, 8)
    )
    + '))    (0||Exceptions()())))'
)


def parse_csv(path: str) -> list[dict]:
    rows = []
    with open(path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 2):
            code = row.get('task_code', '').strip()
            if not code:
                continue
            dur_str = row.get('duration_days', '0').strip() or '0'
            rows.append({
                'wbs_path': row.get('wbs_path', '').strip(),
                'task_code': code,
                'task_name': row.get('task_name', '').strip(),
                'task_type': row.get('task_type', 'Task').strip(),
                'duration_days': int(float(dur_str)),
                'pred_code': row.get('predecessor_code', '').strip(),
                'rel_type': row.get('rel_type', 'FS').strip(),
                'lag_days': int(float(row.get('lag_days', '0').strip() or '0')),
                'constraint_type': (row.get('constraint_type') or '').strip(),
                'constraint_date': (row.get('constraint_date') or '').strip(),
                'row': i,
            })
    return rows


def build_tasks_and_rels(rows: list[dict]) -> tuple[dict, list[tuple]]:
    tasks: dict = {}
    rels: list[tuple] = []

    for r in rows:
        code = r['task_code']
        if code in tasks:
            existing = tasks[code]
            if (existing['task_name'] != r['task_name'] or
                existing['task_type'] != r['task_type'] or
                existing['duration_days'] != r['duration_days']):
                raise ValueError(
                    f'Task {code} has inconsistent definition '
                    f'(row {existing["row"]} vs row {r["row"]})'
                )
        else:
            tasks[code] = {
                'task_name': r['task_name'],
                'task_type': r['task_type'],
                'duration_days': r['duration_days'],
                'wbs_path': r['wbs_path'],
                'constraint_type': r['constraint_type'],
                'constraint_date': r['constraint_date'],
                'row': r['row'],
            }

        if r['pred_code']:
            rels.append((code, r['pred_code'], r['rel_type'], r['lag_days']))

    return tasks, rels


def build_wbs(tasks: dict, proj_id: int) -> tuple[list[dict], dict]:
    wbs_paths: list[str] = []
    seen: set[str] = set()
    for t in tasks.values():
        parts = t['wbs_path'].strip('.').split('.')
        for i in range(1, len(parts) + 1):
            p = '.'.join(parts[:i])
            if p not in seen:
                wbs_paths.append(p)
                seen.add(p)

    wbs_id = ID_OFFSET['wbs']
    wbs_map: dict[str, int] = {}
    wbs_rows: list[dict] = []

    for path in wbs_paths:
        parts = path.split('.')
        name = parts[-1]
        is_root = len(parts) == 1
        parent_path = '.'.join(parts[:-1]) if len(parts) > 1 else ''

        wbs_map[path] = wbs_id
        wbs_rows.append({
            'wbs_id': wbs_id,
            'proj_id': proj_id,
            'wbs_short_name': name,
            'wbs_name': name,
            'parent_wbs_id': wbs_map.get(parent_path, '') if parent_path else '',
            'seq_num': len(wbs_rows) + 1,
            'proj_node_flag': 'Y' if is_root else 'N',
        })
        wbs_id += 1

    # Merge root WBS into P6 project node: remove root, promote children
    if wbs_rows and wbs_rows[0].get('proj_node_flag') == 'Y':
        root_id = wbs_rows[0]['wbs_id']
        root_path = None
        for p in wbs_map:
            if wbs_map[p] == root_id:
                root_path = p
                break
        wbs_rows.pop(0)
        if root_path:
            del wbs_map[root_path]
        for row in wbs_rows:
            if row['parent_wbs_id'] == root_id:
                row['parent_wbs_id'] = ''
        for code, t in tasks.items():
            wp = t['wbs_path'].strip('.')
            if wp in wbs_map:
                continue
            parent = '.'.join(wp.split('.')[:-1])
            if parent in wbs_map:
                wbs_map[wp] = wbs_map[parent]

    task_wbs: dict[str, int] = {}
    for code, t in tasks.items():
        task_wbs[code] = wbs_map.get(t['wbs_path'].strip('.'), list(wbs_map.values())[0])

    return wbs_rows, task_wbs


def _r(values: list) -> str:
    return '%R\t' + '\t'.join(str(v) if v is not None else '' for v in values)


def generate_xer(
    tasks: dict,
    rels: list[tuple],
    project_name: str,
    project_start: str = '2026-01-01',
) -> str:
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    today = datetime.now().strftime('%Y-%m-%d')
    proj_id = ID_OFFSET['project']
    clndr_id = ID_OFFSET['calendar']
    obs_id = 565
    lines: list[str] = []

    lines.append(f'ERMHDR\t7.0\t{today}\tProject\tadmin\tadmin\t\tProject Management\tUSD')

    # OBS
    lines.append('%T\tOBS')
    lines.append('%F\tobs_id\tparent_obs_id\tguid\tseq_num\tobs_name\tobs_descr')
    lines.append(_r([obs_id, None, None, 0, 'Enterprise', '<HTML><BODY></BODY></HTML>']))

    # PROJECT (68 fields)
    lines.append('%T\tPROJECT')
    lines.append(
        '%F\tproj_id\tfy_start_month_num\trsrc_self_add_flag\tallow_complete_flag\t'
        'rsrc_multi_assign_flag\tcheckout_flag\tproject_flag\tstep_complete_flag\t'
        'cost_qty_recalc_flag\tbatch_sum_flag\tname_sep_char\tdef_complete_pct_type\t'
        'proj_short_name\tacct_id\torig_proj_id\tsource_proj_id\tbase_type_id\t'
        'clndr_id\tsum_base_proj_id\ttask_code_base\ttask_code_step\tpriority_num\t'
        'wbs_max_sum_level\tstrgy_priority_num\tlast_checksum\tcritical_drtn_hr_cnt\t'
        'def_cost_per_qty\tlast_recalc_date\tplan_start_date\tplan_end_date\t'
        'scd_end_date\tadd_date\tlast_tasksum_date\tfcst_start_date\t'
        'def_duration_type\ttask_code_prefix\tguid\tdef_qty_type\tadd_by_name\t'
        'web_local_root_path\tproj_url\tdef_rate_type\tadd_act_remain_flag\t'
        'act_this_per_link_flag\tdef_task_type\tact_pct_link_flag\tcritical_path_type\t'
        'task_code_prefix_flag\tdef_rollup_dates_flag\tuse_project_baseline_flag\t'
        'rem_target_link_flag\treset_planned_flag\tallow_neg_act_flag\t'
        'sum_assign_level\tlast_fin_dates_id\tlast_baseline_update_date\t'
        'cr_external_key\tapply_actuals_date\tlocation_id\tloaded_scope_level\t'
        'export_flag\tnew_fin_dates_id\tbaselines_to_export\t'
        'baseline_names_to_export\tnext_data_date\tclose_period_flag\t'
        'sum_refresh_date\ttrsrcsum_loaded'
    )
    lines.append(_r([
        proj_id, 1, 'Y', 'Y', 'Y', 'N', 'Y', 'N', 'N', 'Y',
        '.', 'CP_Drtn', project_name, None, None, None, None,
        clndr_id, None, 1000, 10, 10, 2, 500,
        None, 0, 0.0000, now, f'{project_start} 08:00', None,
        None, now, None, None,
        'DT_FixedDUR2', 'A', None, 'QT_Hour', 'admin',
        None, None, 'COST_PER_QTY', 'N', 'Y',
        'TT_Task', 'Y', 'CT_TotFloat', 'Y', 'Y', 'Y', 'Y',
        'N', 'N', 'SL_Taskrsrc',
        None, None, None, None, None,
        7, 'Y',
        None, None, None, None, None, None, None,
    ]))

    # CALENDAR (13 fields)
    lines.append('%T\tCALENDAR')
    lines.append(
        '%F\tclndr_id\tdefault_flag\tclndr_name\tproj_id\tbase_clndr_id\t'
        'last_chng_date\tclndr_type\tday_hr_cnt\tweek_hr_cnt\tmonth_hr_cnt\t'
        'year_hr_cnt\trsrc_private\tclndr_data'
    )
    lines.append(_r([
        clndr_id, 'Y', '7Day-8h', None, None,
        now, 'CA_Base', HPD, HPD * 7, HPD * 30, HPD * 365,
        'N', CLNDR_DATA,
    ]))

    # SCHEDOPTIONS (25 fields)
    lines.append('%T\tSCHEDOPTIONS')
    lines.append(
        '%F\tschedoptions_id\tproj_id\tsched_outer_depend_type\tsched_open_critical_flag\t'
        'sched_lag_early_start_flag\tsched_retained_logic\tsched_setplantoforecast\t'
        'sched_float_type\tsched_calendar_on_relationship_lag\tsched_use_expect_end_flag\t'
        'sched_progress_override\tlevel_float_thrs_cnt\tlevel_outer_assign_flag\t'
        'level_outer_assign_priority\tlevel_over_alloc_pct\tlevel_within_float_flag\t'
        'level_keep_sched_date_flag\tlevel_all_rsrc_flag\t'
        'sched_use_project_end_date_for_float\tenable_multiple_longest_path_calc\t'
        'limit_multiple_longest_path_calc\tmax_multiple_longest_path\t'
        'use_total_float_multiple_longest_paths\tkey_activity_for_multiple_longest_paths\t'
        'LevelPriorityList'
    )
    lines.append(_r([
        1, proj_id, 'SD_Both', 'N', 'Y', 'Y', 'N', 'FT_FF',
        'rcal_Predecessor', 'Y', 'N', 0, 'N', 5, 25, 'N', 'Y',
        'Y', 'Y', 'N', 'Y', 10, 'Y', None, 'priority_type,ASC',
    ]))

    # PROJWBS (26 fields)
    wbs_rows, task_wbs = build_wbs(tasks, proj_id)
    lines.append('%T\tPROJWBS')
    lines.append(
        '%F\twbs_id\tproj_id\tobs_id\tseq_num\test_wt\tproj_node_flag\t'
        'sum_data_flag\tstatus_code\twbs_short_name\twbs_name\tphase_id\t'
        'parent_wbs_id\tev_user_pct\tev_etc_user_value\torig_cost\t'
        'indep_remain_total_cost\tann_dscnt_rate_pct\tdscnt_period_type\t'
        'indep_remain_work_qty\tanticip_start_date\tanticip_end_date\t'
        'ev_compute_type\tev_etc_compute_type\tguid\ttmpl_guid\tplan_open_state'
    )
    for w in wbs_rows:
        lines.append(_r([
            w['wbs_id'], w['proj_id'], obs_id, w['seq_num'], 1,
            w['proj_node_flag'], 'N', 'WS_Open',
            w['wbs_short_name'], w['wbs_name'], None,
            w['parent_wbs_id'],
            6, 0.88, 0.0000, 0.0000,
            None, None, None, None, None,
            'EC_Cmp_pct', 'EE_Rem_hr', None, None, None,
        ]))

    # TASK (60 fields)
    tid = ID_OFFSET['task']
    code2id: dict[str, int] = {}
    lines.append('%T\tTASK')
    lines.append(
        '%F\ttask_id\tproj_id\twbs_id\tclndr_id\tphys_complete_pct\t'
        'rev_fdbk_flag\test_wt\tlock_plan_flag\tauto_compute_act_flag\t'
        'complete_pct_type\ttask_type\tduration_type\tstatus_code\t'
        'task_code\ttask_name\trsrc_id\ttotal_float_hr_cnt\tfree_float_hr_cnt\t'
        'remain_drtn_hr_cnt\tact_work_qty\tremain_work_qty\ttarget_work_qty\t'
        'target_drtn_hr_cnt\ttarget_equip_qty\tact_equip_qty\tremain_equip_qty\t'
        'cstr_date\tact_start_date\tact_end_date\tlate_start_date\tlate_end_date\t'
        'expect_end_date\tearly_start_date\tearly_end_date\trestart_date\treend_date\t'
        'target_start_date\ttarget_end_date\trem_late_start_date\trem_late_end_date\t'
        'cstr_type\tpriority_type\tsuspend_date\tresume_date\tfloat_path\t'
        'float_path_order\tguid\ttmpl_guid\tcstr_date2\tcstr_type2\t'
        'driving_path_flag\tact_this_per_work_qty\tact_this_per_equip_qty\t'
        'external_early_start_date\texternal_late_end_date\tcreate_date\t'
        'update_date\tcreate_user\tupdate_user\tlocation_id'
    )
    for code, t in tasks.items():
        is_ms = t['task_type'] == 'Milestone'
        task_type = 'TT_FinMile' if is_ms else 'TT_Task'
        drtn_hr = 0 if is_ms else t['duration_days'] * HPD

        cstr_type = t.get('constraint_type') or None
        cstr_date = None
        if t.get('constraint_date'):
            try:
                dt = datetime.strptime(t['constraint_date'], '%Y-%m-%d')
                cstr_date = dt.strftime('%Y-%m-%d 08:00')
            except ValueError:
                cstr_date = None

        lines.append(_r([
            tid, proj_id, task_wbs[code], clndr_id,
            0, 'N', 1, 'N', 'N', 'CP_Drtn',
            task_type, 'DT_FixedDUR2', 'TK_NotStart',
            code, t['task_name'], None,
            0, 0, drtn_hr,
            0, 0, 0, drtn_hr,
            0, 0, 0,
            cstr_date, None, None, None, None, None,
            None, None, None, None, None, None,
            None, None,
            cstr_type, 'PT_Normal', None, None, None,
            None, None, None, None, None,
            None, None, None, None, None,
            now, now, 'admin', 'admin', None,
        ]))
        code2id[code] = tid
        tid += 1

    # TASKPRED (10 fields)
    pid = ID_OFFSET['taskpred']
    lines.append('%T\tTASKPRED')
    lines.append(
        '%F\ttask_pred_id\ttask_id\tpred_task_id\tproj_id\tpred_proj_id\t'
        'pred_type\tlag_hr_cnt\tfloat_path\taref\tarls'
    )
    for succ, pred, rtype, lag in rels:
        lines.append(_r([
            pid, code2id[succ], code2id[pred], proj_id, proj_id,
            f'PR_{rtype}', lag * HPD, None, None, None,
        ]))
        pid += 1

    lines.append('')
    return '\r\n'.join(lines)


def convert(
    csv_path: str,
    xer_path: str,
    project_name: str = 'Construction Schedule',
    project_start: str = '2026-01-01',
) -> int:
    """Convert CSV to XER. Returns XER file size in bytes."""
    rows = parse_csv(csv_path)
    tasks, rels = build_tasks_and_rels(rows)
    print(f'Parsed: {len(tasks)} tasks, {len(rels)} relationships')

    validate_network(tasks, rels)

    xer = generate_xer(tasks, rels, project_name, project_start)
    with open(xer_path, 'wb') as f:
        f.write(xer.encode('utf-8'))

    print(f'XER saved: {xer_path} ({len(xer)} bytes)')
    print('Next: Import in P6 via File → Import → XER, then press F9 to schedule.')
    return len(xer)
