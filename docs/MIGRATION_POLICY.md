# Database Migration Policy

To support true zero-downtime deployments in Azure Container Apps, **all database migrations must be fully backward-compatible**. 

Because our CI/CD pipeline runs `psql` migrations *before* the new backend containers finish booting, there is a 1-3 minute window where the **old code** is running against the **new database schema**.

## The Golden Rule
**You may never alter or drop a column that is currently in use.**

### ✅ Allowed (Expand)
- Creating new tables.
- Adding new nullable columns.
- Adding new columns with a default value.
- Creating indexes.

### ❌ Strictly Forbidden (Contract)
- `DROP TABLE`
- `DROP COLUMN`
- `ALTER TABLE ... RENAME COLUMN`
- Changing a column type in an incompatible way.
- Adding a `NOT NULL` column without a default value.

## How to Rename or Drop a Column (The Expand/Contract Pattern)

If you must rename or remove a column, it requires a **multi-phase deployment** spread across several days:

### Phase 1: Expand
1. Add the new column (e.g., `last_name`).
2. Update the application code to write to *both* the old column (`surname`) and the new column (`last_name`), but continue reading from the old column.
3. **Deploy to Production.**

### Phase 2: Migrate Data
1. Run a backfill script to copy all existing data from `surname` to `last_name`.

### Phase 3: Transition
1. Update the application code to strictly read and write from the *new* column (`last_name`).
2. **Deploy to Production.**

### Phase 4: Contract (Days Later)
1. Now that the old column `surname` is completely unused by any running code, you may create a migration with `DROP COLUMN surname`.
2. **Deploy to Production.**
