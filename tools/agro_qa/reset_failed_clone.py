"""Recreate ONLY this task's incomplete Demo clone after a failed pg_restore."""
import subprocess

database = 'AGRO_INTEGRATION_QA_20261005_DEMO'
root = '/opt/steps-agro-qa/demo'


def sql(query):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-Atc', query], text=True).strip()


if sql("SELECT count(*) FROM pg_stat_activity WHERE datname='%s'" % database) != '0':
    raise SystemExit('Clone is in use; do not recreate it')
check = subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-d', database, '-Atc',
    "SELECT count(*) FROM pg_extension WHERE extname IN ('pg_trgm','unaccent')"], text=True).strip()
if check != '0':
    raise SystemExit('This is not the expected incomplete clone')
subprocess.run(['sudo', '-u', 'postgres', 'dropdb', database], check=True)
print('Removed only the incomplete task clone for a fresh restore; source STEPS_DEMO is untouched')
