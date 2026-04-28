---
name: p6-schedule-generator
description: AI-assisted construction schedule generation for Primavera P6. Create CSV schedules with CPM validation, produce XER files for P6 import. Covers dual-crane hoisting, parallel foundation work faces, milestone constraint alignment, and network validation.
version: 3.0.0
---

# P6 Schedule Generator — AI Skill

AI creates construction schedule CSV → CPM validates → generates XER → user imports to P6.

## Install

```bash
pip install p6-schedule-toolkit
```

## Commands

```bash
p6-deploy input.csv --project "Project Name" --start 2026-01-01    # CPM validate + generate XER
p6-schedule input.csv --start 2026-01-01 --all                     # CPM only (fast iteration)
p6-to-xer input.csv output.xer --project "Name" --start 2026-01-01 # XER only
```

## Workflow

```
1. Gather requirements from bidding docs
   - Contract milestone dates (7+ control nodes)
   - Equipment count, layout, resource constraints
   - Special site conditions

2. Create CSV schedule file

3. Run p6-schedule --all (pre-validation)
   - Checks: network integrity, circular deps, orphan tasks
   - CPM: forward + backward pass, float, critical path
   - Milestone verification against contract dates
   - Fix any issues before generating XER

4. Run p6-deploy → validates + CPM + generates XER

5. Ask user for P6 database path, delete old project if re-importing

6. User: P6 → File → Import → XER → select file → F9 to schedule

7. Use p6-results-reader skill to verify dates in P6
```

## Pre-Validation Checklist

Before generating XER, always run:

```bash
p6-schedule schedule.csv --start 2026-01-01 --milestones --all
```

Verify ALL of these pass:
- Network validation: no orphan tasks, no circular dependencies
- All contract milestones: actual date ≤ required date
- No completion milestone fires before its phase tasks finish
- Critical path makes logical sense
- Total project end date is reasonable

## CSV Format

```csv
wbs_path,task_code,task_name,task_type,duration_days,predecessor_code,rel_type,lag_days,constraint_type,constraint_date
```

| Field | Description | Example |
|-------|-------------|---------|
| wbs_path | WBS hierarchy, dot-separated | `Section2.Foundation` |
| task_code | Unique ASCII code, numeric preferred | `1100`, `2010`, `3990` |
| task_name | Display name (no ASCII commas, use `、`) | `BJ1 Turbine Foundation` |
| task_type | `Task` or `Milestone` | |
| duration_days | Duration in days, milestone = 0 | `39` |
| predecessor_code | Predecessor task code (empty if none) | `2010` |
| rel_type | `FS` / `SS` / `FF` / `SF` | `FS` |
| lag_days | Lag in days (default 0) | `5` |
| constraint_type | Only `CS_MSO` works (Must Start On) | `CS_MSO` |
| constraint_date | Date for constraint | `2026-05-20` |

**Multiple predecessors**: Repeat task_code on separate rows with different predecessors. Name/type/duration must match exactly.

## Task Code Convention (Numeric, Sortable by Construction Sequence)

```
1xxx  Site Preparation     (1100=start, 1190=prep complete)
2xxx  Foundation Work      (2010-2090=turbines, 2910=first pour, 2990=all complete)
3xxx  Roads & Transformers (3010-3020=roads, 3101-3115=box foundations, 3120=install, 3990=complete)
4xxx  Hoisting             (4010-4025=crane setup, 4110-4190=turbines, 4910=first, 4990=all)
5xxx  Electrical/Comm      (5010-5070=cable/grounding/commissioning, 5990=all grid-ready)
6xxx  Acceptance           (6010-6030=rectification/docs/special, 6990=final acceptance)
```

Milestones: end with `00` (e.g., `2990`). Phase summary milestones: `x990`.

## Scheduling Patterns

### Parallel Foundation Work Faces (SS+N)

Split turbines into groups, each chain starts from project milestone with SS+lagger:

```csv
Section2.Foundation,2010,BJ26 Foundation,Task,38,1100,FS,0,,
Section2.Foundation,2015,BJ18 Foundation,Task,39,2010,SS,5,,
Section2.Foundation,2020,BJ7 Foundation,Task,56,2015,SS,5,,
```

Typical: 3 work faces, SS+5 day stagger.

### Dual-Crane Parallel Hoisting (FS+7)

```csv
Section4.Hoisting,4110,BJ26 Hoisting,Task,14,4025,FS,8,,
Section4.Hoisting,4110,BJ26 Hoisting,Task,14,2010,FS,30,,
Section4.Hoisting,4115,BJ18 Hoisting,Task,14,4110,FS,7,,
Section4.Hoisting,4115,BJ18 Hoisting,Task,14,2015,FS,30,,
```

Each turbine needs BOTH conditions: previous hoist done + 7 days AND own foundation + 30 days curing.

### Commissioning Chain

```
All Hoisting Complete → FS+N → First Commissioning (10d) → FS+M → Grid Test Milestone → FS+1 → All Commissioning (24d) → Grid Ready
```

Tune FS+N and FS+M lags to hit exact milestone dates.

### Phase Completion Milestones (Glue Method)

A completion milestone depends on ALL tasks in its phase via FS+0:

```csv
Section2.Foundation,2990,All Foundations Complete,Milestone,0,2035,FS,0,,
Section2.Foundation,2990,All Foundations Complete,Milestone,0,2065,FS,0,,
Section2.Foundation,2990,All Foundations Complete,Milestone,0,2090,FS,0,,
```

**Common bug**: Missing the LAST task in the chain. Milestone fires before all work is done.

## Constraint Rules

- **Only `CS_MSO`** (Must Start On) is recognized by P6 via XER. Other types silently ignored.
- **Constraints go on milestones only**, not regular tasks.
- **Do not add predecessors to CS_MSO milestones**. If predecessor finishes after constraint date, P6 ignores the constraint and uses the predecessor date.
- **Do not set plan_end_date** (PROJECT field 30). Breaks backward pass / critical path.

## P6 Database Path

Ask the user for their P6 database location. Common locations:

| Platform | Default Path |
|----------|-------------|
| Windows | `%USERPROFILE%\Documents\PPMDBSQLite.db` |
| Config file | `%LOCALAPPDATA%\Oracle\Primavera P6\P6 Professional\PM.ini` |

If user doesn't know, check both locations or ask them to find `PPMDBSQLite.db` on their system.

## Delete Old Project Before Re-import

```python
import sqlite3
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT proj_id FROM PROJECT WHERE proj_short_name = ?", (name,))
pid = cur.fetchone()[0]
for t in ['TASKRSRC', 'TASKPRED']:
    cur.execute(f"DELETE FROM {t} WHERE proj_id = ? OR pred_proj_id = ?", (pid, pid))
for t in ['TASK', 'PROJWBS', 'CALENDAR', 'PROJECT']:
    cur.execute(f"DELETE FROM {t} WHERE proj_id = ?", (pid,))
conn.commit()
```

## Milestone Verification Checklist

After generating, check:

1. All contract milestones meet required dates (not exceeding)
2. No completion milestone fires before all phase tasks finish
3. CS_MSO milestones have NO predecessors
4. Durations and lags are realistic
5. Critical path makes sense (longest chain drives project end)

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| No project after import | %F/%R count mismatch | Verify field counts per table |
| Currency dialog | CURRTYPE table in XER | Remove CURRTYPE |
| Double WBS name | Root WBS in XER + P6 project node | Remove root WBS from XER |
| CS_MSO not applied | Milestone also has predecessor | Remove predecessor from CS_MSO milestone |
| Milestone too early | Missing last-task dependency | Add FS to last task in phase |
| No critical path | plan_end_date set | PROJECT field 30 = None |
| Chinese WBS sort wrong | Alphabetical sort | Keep CSV insertion order |
