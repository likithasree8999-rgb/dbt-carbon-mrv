/*
  assert_blue_carbon_not_empty.sql
  ─────────────────────────────────
  Singular test: fails (returns rows) if the blue carbon mart has
  fewer than 50 projects — indicates a broken merge or source change.
*/

select
    count(*) as project_count,
    'mart_blue_carbon has too few rows — check source merge' as failure_reason
from {{ ref('mart_blue_carbon') }}
having count(*) < 50