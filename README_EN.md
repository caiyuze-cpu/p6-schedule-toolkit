# P6 Schedule Toolkit

**CSV → XER → P6** Construction schedule generation toolkit. Automatically generates Primavera P6-importable XER files from CSV schedules. Suitable for wind power, solar, infrastructure, and other construction scheduling.

## Features

- **AI-Driven**: Works with Claude Code / Cursor / GitHub Copilot — describe your project in natural language, AI generates the CSV schedule
- **CPM Network Validation**: Automatically detects circular dependencies, broken chains, and orphaned nodes
- **P6 Native Compatible**: Generated XER files import directly into Primavera P6 with constraints, milestones, and relationship types
- **Durations Only, No Dates**: P6's scheduling engine calculates all dates and critical paths
- **Result Reading**: Read scheduling results from P6's SQLite database without needing the P6 client

## Quick Start

### Install

```bash
pip install -e .
```

Requires Python 3.10+.

### 1. Create CSV Schedule

Use an AI agent (recommended) or manually edit. CSV format:

```csv
wbs_path,task_code,task_name,task_type,duration_days,predecessor_code,rel_type,lag_days,constraint_type,constraint_date
Site Prep,P1010,Contract Signing,Task,6,,,,
Site Prep,A1000,Start Milestone,Milestone,0,P1010,FS,5,CS_MSO,2026-05-20
Foundation,BJ01_F,BJ01 Foundation,Task,39,A1000,FS,0,,
```

See [docs/csv-format.md](docs/csv-format.md) for full format specification.

### 2. Convert to XER

```bash
p6-to-xer schedule.csv output.xer --project "Section 2 Schedule" --start 2026-05-20
```

### 3. Import to P6

1. Open Primavera P6
2. **File → Import → XER** → select the `.xer` file
3. Open the project, press **F9** to schedule
4. P6 calculates all dates, critical paths, and float automatically

### 4. Read Results

```bash
p6-results --db PPMDBSQLite.db                  # List all projects
p6-results -p "Section 2" --milestones          # Show milestones
p6-results -p "Section 2" --path                # Critical path analysis
p6-results -p "Section 2" --gantt               # Text Gantt chart
```

## Using with AI Agents (Recommended)

This toolkit is designed to work with AI coding assistants:

```
Describe project → AI generates CSV → p6-to-xer converts → Import to P6 → p6-results verifies
```

### Claude Code Skill

Copy the included skill file to `~/.claude/skills/`:

```bash
cp skills/p6-xer-generator.md ~/.claude/skills/
```

Then describe your project to Claude Code (turbine count, contract milestone dates, resource constraints, etc.) and it will automatically generate the CSV, run conversion, and guide you through P6 import.

### Other AI Tools

The `docs/` directory serves as AI reference knowledge:
- `scheduling-guide.md` — Scheduling best practices
- `xer-format.md` — XER format requirements
- `csv-format.md` — CSV format specification
- `troubleshooting.md` — Common issues and fixes

## Constraint Rules

| Constraint | Meaning | Use Case |
|-----------|---------|----------|
| `CS_MSO` | Must Start On | Contract-mandated milestones |

**Critical limitation**: P6 only recognizes `CS_MSO` via XER import. `CS_MFEO`/`CS_MFIN` are silently ignored.

**Only apply constraints to milestones.** Task dates are calculated by P6's scheduler.

**Do not set plan_end_date** (PROJECT table field 30), or P6 will perform backward pass calculation, giving all tasks positive float and hiding the critical path.

## Contributing

Issues and PRs welcome! Especially:

- New industry templates (solar, thermal, transmission)
- P6 version compatibility testing
- Documentation improvements
- Bug fixes and features

## License

MIT
