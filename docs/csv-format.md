# CSV Format Specification

## Columns

```csv
wbs_path,task_code,task_name,task_type,duration_days,predecessor_code,rel_type,lag_days,constraint_type,constraint_date
```

| Column | Required | Description | Example |
|--------|----------|-------------|---------|
| wbs_path | Yes | WBS hierarchy, `.` separated | `Section2.Foundation` |
| task_code | Yes | Unique code, ASCII only | `P1010`, `BJ1_F`, `A1000` |
| task_name | Yes | Task description | `BJ1 Turbine Foundation` |
| task_type | Yes | `Task` or `Milestone` | |
| duration_days | Yes | Duration in days (0 for milestones) | `39` |
| predecessor_code | No | Predecessor task code | `P1050` |
| rel_type | If pred | Relationship type | `FS`/`SS`/`FF`/`SF` |
| lag_days | If pred | Lag in days (negative = lead) | `5`, `-3` |
| constraint_type | No | Constraint type | `CS_MSO` |
| constraint_date | If constraint | Constraint date | `2026-05-20` |

## Multiple Predecessors

A task with multiple predecessors appears on multiple rows. The `task_name`, `task_type`, and `duration_days` must be identical across all rows for the same `task_code`.

```csv
Foundation,A2100,All Foundations Complete,Milestone,0,BJ1_F,FS,0,,
Foundation,A2100,All Foundations Complete,Milestone,0,BJ8_F,FS,0,,
Foundation,A2100,All Foundations Complete,Milestone,0,BJ11_F,FS,0,,
```

## WBS Path

- Use `.` to separate levels: `Section2.Foundation`
- Levels are created automatically in order of appearance
- Keep CSV insertion order — do not sort alphabetically (especially for Chinese names)

## Task Code Rules

- ASCII letters, digits, hyphens, underscores only
- Globally unique across the entire schedule
- No Chinese characters, spaces, or special characters
- Suggested conventions:

```
Site Prep:     P1xxx (tasks), A1xxx (milestones)
Foundation:    BJxx_F (foundation tasks), A2xxx (milestones)
Roads:         ROADx (road sections)
Hoisting:      BJxx_H (hoisting tasks), A4xxx (milestones)
Commissioning: A5xxx (tasks + milestones)
Acceptance:    A6xxx (tasks + milestones)
```

## Relationship Types

```
FS (Finish-Start):  [Pred]━━━▶[Succ]
                    Predecessor must finish before successor starts

SS (Start-Start):   [Pred]━━━━━━━━━━▶
                    [Succ]━━━━━━━▶
                    Successor starts N days after predecessor starts

FF (Finish-Finish): [Pred]━━━━━━━━━━▶
                               [Succ]━━━▶
                    Successor finishes N days after predecessor finishes

SF (Start-Finish):  [Pred]━━━━━━━━━━▶
                    [Succ]━━━▶
                    Successor finishes N days after predecessor starts (rare)
```

## Constraints

Only `CS_MSO` (Must Start On) is supported by P6 via XER import. Other constraint types (`CS_MFEO`, `CS_MFIN`, etc.) are silently ignored.

**Rules:**
- Constraints go on milestones only, not on regular tasks
- Regular task dates are calculated by P6's scheduler from the network logic
- Do not set `plan_end_date` in the project — it causes backward pass calculation that hides the critical path

## 7-Day Work Calendar

The toolkit generates a 7-day work calendar by default:
- Working hours: 08:00-12:00, 13:00-17:00 (8 hours/day)
- All 7 days of the week are working days
- HPD (Hours Per Day) = 8, so `remain_drtn_hr_cnt = days × 8`
