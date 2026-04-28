# CLAUDE.md

## Project: p6-schedule-toolkit

Primavera P6 construction scheduling toolkit. Converts CSV schedules to P6-importable XER files with CPM validation.

## Commands

```bash
pip install -e .                    # Install editable
pytest                              # Run tests
p6-deploy input.csv --start 2026-01-01  # Full workflow: validate + XER
p6-schedule input.csv --all         # CPM analysis only
p6-results -p "Project Name"        # Read P6 database
```

## Architecture

```
src/p6_schedule/
├── csv_to_xer.py    # CSV parser + XER generator
├── cpm_scheduler.py # Forward/backward pass CPM engine
├── validate.py      # Network validation (orphan detection, cycle check)
├── deploy.py        # Combined: validate + CPM + XER
├── read_results.py  # P6 SQLite reader (read-only)
└── cli.py           # CLI entry points
```

## Key Design Decisions

- **XER import only** (no SQLite direct write). SQLite direct write is fragile across P6 versions.
- **CPM engine in Python** for fast iteration. XER is re-generated each time.
- **P6 F9 required** after import. XER contains durations and relationships, not fixed dates.
- **7-day calendar, 8h/day** (HPD=8). All durations in days, converted to hours for XER.
- **FS offset rules**: task→task adds +1 day, milestone→task adds +1 day, task→milestone = same day. This matches P6 behavior.

## CSV Format

```csv
wbs_path,task_code,task_name,task_type,duration_days,predecessor_code,rel_type,lag_days,constraint_type,constraint_date
```

Multiple predecessors: repeat task_code on separate rows. Name/type/duration must match exactly.

## Testing

```bash
pytest tests/ -v
```

Tests cover: validation, CPM forward/backward pass, milestone constraints, SS offset rules, CSV parsing.
