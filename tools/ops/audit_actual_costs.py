"""Read-only coverage and reconciliation audit of the installed actual-cost view."""
import argparse
import json
import re
import subprocess


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--database', required=True)
args = parser.parse_args()
assert args.database in ('LAB_TAREAS', 'CERRO_EL_PLOMO', 'QA-CERROELPLOMO') or re.fullmatch(
    r'MANAGEMENT_QA_(DEVELOPMENT|CERRO|QA-CERRO)_t(?:229|230)_[0-9a-f]{8}(?:_r[1-9][0-9]*)?', args.database)
query = """
BEGIN READ ONLY;
SET LOCAL statement_timeout = '45s';
WITH source AS (
  SELECT id,quantity FROM account_move_line WHERE parent_state='posted'
    AND jsonb_typeof(analytic_distribution)='object' AND analytic_distribution<>'{}'::jsonb
), report AS (
  SELECT move_line_id,SUM(quantity) quantity,SUM(percentage) percentage,
    bool_and(distribution_valid) AS is_valid FROM step_management_actual_cost_report GROUP BY move_line_id
)
SELECT json_build_object(
  'source_lines',(SELECT count(*) FROM source),
  'allocations',(SELECT count(*) FROM step_management_actual_cost_report),
  'coverage_errors',(SELECT count(*) FROM source s FULL JOIN report r ON r.move_line_id=s.id
    WHERE s.id IS NULL OR r.move_line_id IS NULL),
  'quantity_errors',(SELECT count(*) FROM source s JOIN report r ON r.move_line_id=s.id
    WHERE r.is_valid AND abs(s.quantity-r.quantity)>0.000001),
  'weight_errors',(SELECT count(*) FROM report WHERE is_valid AND abs(percentage-100)>0.00001),
  'source_distributions_to_review',(SELECT count(*) FROM report WHERE NOT is_valid),
  'duplicate_ids',(SELECT count(*) FROM (SELECT id FROM step_management_actual_cost_report GROUP BY id HAVING count(*)>1) d),
  'browser_id_errors',(SELECT count(*) FROM step_management_actual_cost_report WHERE id>9007199254740991 OR id<=0),
  'missing_plan_roles',(SELECT count(*) FROM res_company c WHERE c.id IN (
    SELECT DISTINCT company_id FROM step_management_actual_cost_report) AND
    (management_actual_season_plan_id IS NULL OR management_actual_center_plan_id IS NULL OR management_actual_activity_plan_id IS NULL))
);
ROLLBACK;
"""
result = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1',
    '-d', args.database, '-f', '-'], input=query, text=True, capture_output=True)
assert result.returncode == 0, result.stderr
proof = json.loads(result.stdout)
for field in ('coverage_errors', 'quantity_errors', 'weight_errors', 'duplicate_ids', 'browser_id_errors', 'missing_plan_roles'):
    assert proof[field] == 0, (field, proof)
print('ACTUAL_COSTS_LEDGER_AUDIT_OK ' + json.dumps(dict(database=args.database, **proof)))
