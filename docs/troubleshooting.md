# Troubleshooting

## Import Issues

### P6 shows no project after XER import

**Cause**: %F field count doesn't match %R value count in one or more tables.

**Fix**: Check each table's %F header and count the tab-separated fields. Each %R row must have exactly the same number of values. P6 silently rejects the entire file with no error.

### Currency dialog blocks import

**Cause**: XER file contains a CURRTYPE table.

**Fix**: Remove all CURRTYPE-related lines from the XER. The toolkit does not generate this table.

### Double \r in line endings

**Cause**: Used `open(file, 'w')` text mode on Windows.

**Fix**: Use binary mode: `open(file, 'wb').write(content.encode('utf-8'))`. The toolkit handles this correctly.

## Scheduling Issues

### No critical path (all tasks have positive float)

**Cause**: `plan_end_date` is set in the PROJECT table (field 30).

**Fix**: Set `plan_end_date` to None/empty. P6 performs backward pass from this date, giving all tasks positive float and hiding the critical path.

### Zero-float tasks not flagged as critical

**Cause**: Python `0 or 999 = 999` bug — zero is falsy.

**Fix**: Use `f is not None and f <= 0` instead of `f or 999 <= 0`.

### CS_MFEO / CS_MFIN constraints have no effect

**Cause**: P6 XER import only recognizes `CS_MSO`.

**Fix**: Use only `CS_MSO` for all constraints. P6 silently ignores other constraint types.

### Milestone has unexpected float

**Cause**: Milestone has multiple predecessors but also a CS_MSO constraint.

**Fix**: The constraint overrides network logic. This is expected behavior — the milestone date is fixed regardless of predecessor calculations.

## CSV Issues

### WBS order is wrong

**Cause**: Used `sorted()` on Chinese WBS names.

**Fix**: Keep CSV insertion order. The toolkit preserves the order tasks appear in the CSV.

### CSV comma in task name treated as separator

**Cause**: Task name contains ASCII commas.

**Fix**: Use Chinese comma `、` instead of `,` in task names.

### Task has inconsistent definition

**Cause**: Same `task_code` appears with different `task_name`, `task_type`, or `duration_days` across rows.

**Fix**: When defining multiple predecessors for the same task, ensure all non-relationship fields are identical.

## P6 Database Issues

### Database is locked

**Cause**: P6 is running and holding the database.

**Fix**: Close P6 before reading, or use read-only mode (`?mode=ro` URI parameter). The toolkit uses read-only mode by default.

### Deleting old projects

To clean up old projects in P6's SQLite database:

```python
import sqlite3

conn = sqlite3.connect(db_path)
for table in ['TASKPRED', 'TASK', 'PROJWBS', 'CALENDAR']:
    conn.execute(f'DELETE FROM {table} WHERE proj_id = ?', (proj_id,))
conn.execute('DELETE FROM PROJECT WHERE proj_id = ?', (proj_id,))
conn.commit()
conn.close()
```

**Warning**: Always back up the database before direct manipulation. Close P6 first.
