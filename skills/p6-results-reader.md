---
name: p6-results-reader
description: Read and analyze Primavera P6 SQLite database results. Check scheduled dates, milestones, critical path, and compare against contract requirements. For use after P6 import and F9 scheduling.
version: 3.0.0
---

# P6 Results Reader — AI Skill

Read P6 SQLite database to verify scheduled dates, analyze critical path, and compare against contract milestones.

## Install

```bash
pip install p6-schedule-toolkit
```

## Commands

```bash
p6-results                                              # List all projects
p6-results -p "Project Name"                            # Show all tasks
p6-results -p "Project Name" --milestones               # Milestones only
p6-results -p "Project Name" --critical                 # Critical path
p6-results -p "Project Name" --gantt                    # Text Gantt chart
p6-results -p "Project Name" --rels                     # All relationships
p6-results -p "Project Name" --path                     # Critical path analysis
```

Database path: use `--db` flag if not default. Default searches current directory for `PPMDBSQLite.db`.

## P6 Database Location

Ask the user for their database path, or check common locations:

| Platform | Default Path |
|----------|-------------|
| Windows | `%USERPROFILE%\Documents\PPMDBSQLite.db` |
| Config | `%LOCALAPPDATA%\Oracle\Primavera P6\P6 Professional\PM.ini` |

```bash
# User provides path
p6-results -d "C:/Users/user/Documents/PPMDBSQLite.db" -p "Project Name"
```

## Workflow

```
1. User imports XER into P6 and presses F9 to schedule
2. User closes P6 (releases database lock)
3. Run p6-results to read scheduled dates
4. Compare against contract milestone requirements
5. If dates don't match, go back to p6-schedule-generator to adjust CSV
```

**Important**: P6 must be closed before reading the database, otherwise it's locked.

## Reading P6 Dates

P6 stores dates as datetime strings in TASK table:

| Column | Meaning |
|--------|---------|
| `early_start_date` / `early_end_date` | Scheduled dates after F9 |
| `target_start_date` / `target_end_date` | Planned dates |
| `total_float_hr_cnt` | Total float in hours (0 = critical) |
| `cstr_type` / `cstr_date` | Constraint type and date |

Date conventions:
- Tasks: start = 08:00, end = 17:00
- Milestones: start = end (same timestamp, usually 17:00 for end-of-day or 08:00 for start-of-day)
- Compare date portion only, ignore time

### Critical Task Detection

```python
def is_critical(task):
    f = task.get('total_float_hr_cnt')
    return f is not None and f <= 0  # 0 is falsy in Python, must check explicitly!
```

## Analysis Workflow

### 1. Verify Milestone Dates

```bash
p6-results -p "Project Name" --milestones
```

Compare each milestone against contract dates. Flag any that exceed requirements.

### 2. Check Critical Path

```bash
p6-results -p "Project Name" --critical
p6-results -p "Project Name" --path
```

Verify the critical path makes logical sense. The longest chain should drive the project end date.

### 3. Full Schedule Review

```bash
p6-results -p "Project Name"
```

Check for:
- Tasks with negative float (behind schedule before starting)
- Tasks with excessive float (too much buffer)
- Milestones that complete before all phase tasks finish (bug in CSV)
- Unexpected date shifts from CPM vs Python engine

### 4. Compare with Python CPM

If P6 dates differ from `p6-schedule` output, check:
- CS_MSO constraint ignored? → Milestone has predecessor finishing after constraint date
- Dates shifted by 1 day? → FS offset rule: task→task +1, milestone→task +1, task→milestone = 0
- WBS issues? → Check WBS hierarchy in P6 matches CSV

## Relationship Analysis

```bash
p6-results -p "Project Name" --rels
```

Shows all predecessor-successor relationships with lag values. Useful for debugging why a task starts later than expected.

## Text Gantt Chart

```bash
p6-results -p "Project Name" --gantt
```

Displays a text-based Gantt chart for quick visual review of the schedule timeline.

## Common P6 Scheduling Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Milestone date wrong | CS_MSO + predecessor conflict | Remove predecessor from constrained milestone |
| All tasks same date | F9 not pressed | Press F9 in P6 after import |
| DB locked error | P6 is running | Close P6, then read database |
| No critical path | plan_end_date set in XER | Regenerate XER without plan_end_date |
| Float shows as 999 | Python `0 or 999` bug | Use `f is not None and f <= 0` |
| Dates shifted 1 day | FS offset difference | Check P6 FS rules vs CSV assumptions |
