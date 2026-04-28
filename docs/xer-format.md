# XER Format Requirements

## File Structure

The generated XER file contains 7 required tables:

```
ERMHDR\t7.0\tYYYY-MM-DD\tProject\tadmin\tadmin\t\tProject Management\tUSD
%T\tOBS          → %F → %R (1 row)
%T\tPROJECT      → %F → %R (68 fields, 1 row)
%T\tCALENDAR     → %F → %R (13 fields, 1 row)
%T\tSCHEDOPTIONS → %F → %R (25 fields, 1 row)
%T\tPROJWBS      → %F → %R (26 fields, multiple rows)
%T\tTASK         → %F → %R (60 fields, multiple rows)
%T\tTASKPRED     → %F → %R (10 fields, multiple rows)
(blank line at end)
```

## Critical Rules

### Field Count Alignment (CRITICAL)

Each `%R` row's tab-separated value count **must exactly match** its corresponding `%F` header. If they don't match, P6 silently rejects the entire file with no error message.

### Encoding and Line Endings

- **UTF-8 encoding**
- **CRLF line endings** (`\r\n`)
- Must use binary write mode: `open(file, 'wb').write(content.encode('utf-8'))`
- Do not use text mode `open(file, 'w')` — Windows double-escapes `\r`

### Tables NOT to Include

- **CURRTYPE**: Including this table triggers a currency matching dialog that blocks import
- Any table not listed above is unnecessary

## PROJECT Table (68 Fields)

Key fields:

| Field # | Name | Value | Notes |
|---------|------|-------|-------|
| 13 | proj_short_name | Project display name | |
| 18 | clndr_id | Calendar ID | Must match CALENDAR table |
| 29 | plan_start_date | `YYYY-MM-DD HH:MM` | Project start |
| 30 | plan_end_date | **None** | MUST be empty, or critical path breaks |
| 35 | def_duration_type | `DT_FixedDUR2` | Fixed duration |
| 45 | def_task_type | `TT_Task` | Default task type |
| 47 | critical_path_type | `CT_TotFloat` | Total float based |

## TASK Table (60 Fields)

Key fields:

| Field # | Name | Value | Notes |
|---------|------|-------|-------|
| 11 | task_type | `TT_Task` or `TT_FinMile` | Milestone = TT_FinMile |
| 12 | duration_type | `DT_FixedDUR2` | |
| 13 | status_code | `TK_NotStart` | |
| 19 | remain_drtn_hr_cnt | days × 8 | 0 for milestones |
| 23 | target_drtn_hr_cnt | Same as #19 | |
| 26 | cstr_date | `YYYY-MM-DD 08:00` | Constraint date |
| 40 | cstr_type | `CS_MSO` | Only this type works |

Milestones: `drtn_hr_cnt = 0`, `task_type = TT_FinMile`

## TASKPRED Table (10 Fields)

Key fields:

| Field # | Name | Value | Notes |
|---------|------|-------|-------|
| 6 | pred_type | `PR_FS`/`PR_SS`/`PR_FF`/`PR_SF` | |
| 7 | lag_hr_cnt | lag_days × 8 | |

## Calendar Data Format

```
(0||CalendarData()(    (0||DaysOfWeek()(
      (0||1()(        (0||0(s|08:00|f|12:00)())        (0||1(s|13:00|f|17:00)())))
      ...for days 1-7...
))    (0||Exceptions()())))
```

For 7-day work week: days 1-7 all have work periods (08:00-12:00, 13:00-17:00).

## P6 Date Arithmetic

P6 schedules using CPM with these rules:
- **FS+N**: Successor starts approximately N+1 days after predecessor ends
- **SS+N**: Successor starts N days after predecessor starts
- The "+1 day" offset on FS is due to P6's date alignment on working day boundaries
- Milestones (0 duration) get a single date, not a range
