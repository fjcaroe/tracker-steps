"""Configure only the native Cosechero job after exact Harvest copy certification.

Run as root with review proxies stopped. Copy mode is the default; --apply is
the only committing mode. Live mode additionally requires the matching deploy
backup and configuration plus crew-smoke proofs from all three private copies.
"""
import argparse
import configparser
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


ENVIRONMENTS = ('development', 'cerro', 'qa-cerro')
BACKEND_COMMIT = '8c76d2262113b82fc6217987fea95cb5bff8882c'
COMPANY_ID, USER_ID = 1, 6
MARKER = 'HARVEST_DEFAULT_JOB_RESULT '
COPY_PROOF = 'harvest-default-job-copy.json'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def stage_identity(environment):
    assert environment in ENVIRONMENTS
    suffix = 't236237_' + BACKEND_COMMIT[:8]
    return 'management_' + environment + '_' + suffix, 'MANAGEMENT_QA_' + environment.upper() + '_' + suffix


def validate_certificate(environment, stage_name, proof, package_sha, release):
    expected_stage, database = stage_identity(environment)
    assert stage_name == expected_stage and proof['database'] == database, 'Exact certified destination copy required'
    assert proof['environment'] == environment and proof['feature'] == 'harvest-app'
    assert proof['commit'] == release['commit'] == BACKEND_COMMIT
    assert proof['release_sha256'] == package_sha and re.fullmatch('[a-f0-9]{64}', package_sha)
    assert proof['business_preserved'] is True and not proof.get('readonly_copy')
    assert release['versions']['step_harvest_launcher'] == '18.0.1.4.0'


def read_release(package):
    assert package.is_file() and not package.is_symlink()
    with tarfile.open(package) as archive:
        members = archive.getmembers()
        names = [item.name for item in members]
        assert len(names) == len(set(names)) and names.count('release.json') == 1
        assert all(item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts for item in members)
        release = json.load(archive.extractfile('release.json'))
        assert set(names) == set(release['files']) | {'release.json'}
        for item in members:
            if item.name != 'release.json':
                assert hashlib.sha256(archive.extractfile(item).read()).hexdigest() == release['files'][item.name]
    return release


def verify_files(root, release):
    assert root.is_dir() and not root.is_symlink() and root.resolve() == root
    for name, expected in release['files'].items():
        path = root / name
        assert path.resolve().is_relative_to(root) and not path.is_symlink() and path.is_file()
        assert digest(path) == expected, 'The loaded backend differs from the certified package'


def validate_configuration_proof(value, environment, package_sha, helper_sha):
    stage_name, database = stage_identity(environment)
    assert value['mode'] == 'copy' and value['applied'] is True
    assert value['environment'] == environment and value['stage'] == stage_name and value['database'] == database
    assert value['commit'] == BACKEND_COMMIT and value['release_sha256'] == package_sha
    assert value['helper_sha256'] == helper_sha
    assert value['company_id'] == COMPANY_ID and value['user_id'] == USER_ID
    assert type(value['job_id']) is int and value['job_id'] > 0
    assert all(value.get(key) is True for key in ('previous_jobs_preserved', 'employees_preserved', 'roles_preserved', 'permissions_preserved'))


def validate_crew_smoke(value, configuration, environment, package_sha, helper_sha):
    stage_name, database = stage_identity(environment)
    assert value['stage'] == stage_name and value['database'] == database and value['feature'] == 'harvest-app'
    assert value['backend_commit'] == BACKEND_COMMIT and value['backend_sha256'] == package_sha
    assert value['default_job_helper_sha256'] == helper_sha and value['native_job_id'] == configuration['job_id']
    assert value['company_id'] == COMPANY_ID and value['user_id'] == USER_ID
    assert all(type(value.get(key)) is int and value[key] > 0 for key in ('native_worker_id', 'native_attendance_id', 'native_crew_id'))
    assert value['new_workers'] == value['new_attendances'] == 1
    assert all(value.get(key) is True for key in ('worker_enrollment', 'crew_attendance', 'attendance_home_total',
        'native_job_default', 'scope_rejected_before_write', 'enrollment_idempotency', 'attendance_idempotency',
        'changed_hours_rejected', 'wrong_date_rejected', 'native_context', 'native_members_preserved'))
    assert value['credentials_or_session_ids_supplied'] is False
    assert datetime.fromisoformat(value['created_at']) >= datetime.fromisoformat(configuration['created_at'])


def bind_configuration_smoke(evidence, configuration, environment, package_sha, helper_sha):
    validate_configuration_proof(configuration, environment, package_sha, helper_sha)
    assert evidence['native_job_id'] == configuration['job_id']
    assert evidence['company_id'] == COMPANY_ID and evidence['user_id'] == USER_ID
    return dict(evidence, default_job_helper_sha256=helper_sha)


def validate_backup(environment, backup, deployment, package_sha, first_addons):
    expected_root = Path('/opt/steps-managed/releases') / environment / BACKEND_COMMIT
    assert backup.parent == Path('/opt/steps_backups') and re.fullmatch(
        'management_' + re.escape(environment) + r'_\d{8}T\d{6}Z', backup.name)
    assert backup.resolve() == backup and not backup.is_symlink()
    dump = backup / 'database.dump'
    assert dump.is_file() and not dump.is_symlink() and dump.stat().st_size > 0
    assert deployment['commit'] == BACKEND_COMMIT and deployment['sha256'] == package_sha
    assert deployment['overlay'] == str(expected_root) and first_addons == expected_root
    assert isinstance(deployment['log'], str) and PurePosixPath(deployment['log']).is_absolute()


def validate_all_copies(stages_root, package_sha, helper_sha, release):
    for environment in ENVIRONMENTS:
        stage = stages_root / stage_identity(environment)[0]
        assert stage.resolve() == stage and not stage.is_symlink()
        proof = json.loads((stage/'qa_passed.json').read_text())
        validate_certificate(environment, stage.name, proof, package_sha, release)
        configuration = json.loads((stage/COPY_PROOF).read_text())
        validate_configuration_proof(configuration, environment, package_sha, helper_sha)
        smoke = json.loads((stage/'harvest-crew-smoke.json').read_text())
        validate_crew_smoke(smoke, configuration, environment, package_sha, helper_sha)


SCRIPT = r'''
import hashlib
import json
assert env.cr.dbname == PLAN['database']
env.cr.execute("SET LOCAL lock_timeout = '5s'")
env.cr.execute('LOCK TABLE hr_job IN SHARE ROW EXCLUSIVE MODE')
company = env['res.company'].browse(1).exists()
user = env['res.users'].browse(6).exists()
assert company and user and user.active and not user.share and company in user.company_ids
assert PLAN['company_id'] == company.id == 1 and PLAN['user_id'] == user.id == 6
business = env(user=user, su=False, context=dict(env.context, allowed_company_ids=[1]))
assert business['hr.employee'].has_access('create'), 'The existing review profile cannot enroll employees'
def roles():
    env.invalidate_all()
    return user.read(['active','share','groups_id','company_id','company_ids'])[0]
def permissions():
    return {model: business[model].has_access('create') for model in ('hr.employee','hr.job','hr.attendance')}
def rows(table):
    scope = ' WHERE company_id=1' if table == 'hr_employee' else ''
    env.cr.execute('SELECT id, md5(to_jsonb(t)::text) FROM '+table+' t'+scope+' ORDER BY id')
    return env.cr.fetchall()
def snapshot_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
before_jobs, before_employees = rows('hr_job'), rows('hr_employee')
before_roles, before_permissions = roles(), permissions()
jobs = env['hr.job'].with_context(active_test=False, tracking_disable=True, mail_create_nolog=True,
                                  mail_create_nosubscribe=True, mail_notrack=True)
matches = jobs.search([('name','=ilike','Cosechero'),('company_id','in',[False,1])])
assert len(matches) <= 1, 'Several native Cosechero jobs require explicit master review'
created = not bool(matches)
if matches:
    job = matches
    assert 'active' not in job._fields or job.active, 'The existing Cosechero job is archived; preserve it for review'
else:
    values = {'name':'Cosechero','company_id':1}
    if 'no_of_recruitment' in jobs._fields: values['no_of_recruitment'] = 0
    job = jobs.create(values)
env.flush_all()
after_jobs = rows('hr_job')
assert [row for row in after_jobs if row[0] in {item[0] for item in before_jobs}] == before_jobs
assert len(after_jobs) == len(before_jobs) + int(created)
assert rows('hr_employee') == before_employees, 'Configuration changed employees'
assert roles() == before_roles, 'Configuration changed the existing user roles or companies'
assert permissions() == before_permissions, 'Configuration changed native permissions'
visible = business['hr.job'].search([('name','=ilike','Cosechero'),('company_id','in',[False,1])])
assert visible.ids == job.ids, 'The existing review profile cannot read the configured native job'
result = dict(PLAN, job_id=job.id, created=created, applied=PLAN['apply'],
              previous_jobs_preserved=True, employees_preserved=True, roles_preserved=True, permissions_preserved=True,
              employee_count=len(before_employees), previous_job_count=len(before_jobs),
              previous_jobs_sha256=snapshot_digest(before_jobs), employees_sha256=snapshot_digest(before_employees),
              roles_sha256=snapshot_digest(before_roles),
              permissions=before_permissions)
result.pop('apply')
if PLAN['apply']: env.cr.commit()
else: env.cr.rollback()
print('HARVEST_DEFAULT_JOB_RESULT '+json.dumps(result, sort_keys=True))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=ENVIRONMENTS)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Run this configuration tool as root'
    assert not args.live or args.backup, 'Live configuration requires the matching deployment backup'
    assert args.live or args.backup is None, '--backup belongs only to live configuration'
    stage, package = args.stage, args.package
    assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation') and not stage.is_symlink()
    assert package.resolve() == package
    proof = json.loads((stage/'qa_passed.json').read_text())
    package_sha, helper_sha = digest(package), digest(Path(__file__).resolve())
    release = read_release(package)
    validate_certificate(args.environment, stage.name, proof, package_sha, release)
    verify_files(stage/'addons', release)
    assert (stage/'data').is_dir() and not (stage/'data').is_symlink()
    root = Path(__file__).resolve().parent
    target = json.loads((root/'environments.json').read_text())['environments'][args.environment]
    config = configparser.ConfigParser(interpolation=None)
    assert config.read(target['config'])
    options = config['options']
    assert options['db_name'] == target['database']
    config_sha = digest(Path(target['config']))
    mode = 'live' if args.live else 'copy'
    output = stage / ('harvest-default-job-' + mode + ('' if args.apply else '-dry-run') + '.json')
    assert not output.exists() and not output.is_symlink(), 'Keep previous configuration evidence; do not overwrite it'
    database = target['database'] if args.live else proof['database']
    if args.live:
        deployment = json.loads((args.backup/'deployment.json').read_text())
        first_addons = Path(options['addons_path'].split(',')[0].strip())
        validate_backup(args.environment, args.backup, deployment, package_sha, first_addons)
        verify_files(first_addons, release)
        validate_all_copies(stage.parent, package_sha, helper_sha, release)
    service_user = subprocess.check_output(['systemctl','show','--value','--property=User',target['service']], text=True).strip()
    assert re.fullmatch(r'[a-z_][a-z0-9_-]*\$?', service_user)
    command = ['sudo','-u',service_user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell',
               '-c',target['config'],'-d',database,'--db-filter=^'+database+'$','--no-http',
               '--workers=0','--max-cron-threads=0','--log-level=error']
    if not args.live:
        command += ['--addons-path='+str(stage/'addons')+','+options['addons_path'], '--data-dir='+str(stage/'data')]
    plan = {'environment':args.environment, 'mode':mode, 'stage':stage.name, 'database':database,
            'company_id':COMPANY_ID, 'user_id':USER_ID, 'commit':BACKEND_COMMIT,
            'release_sha256':package_sha, 'helper_sha256':helper_sha, 'apply':args.apply}
    # Linux-only helpers stay below main so the pure guards can be tested on Windows.
    import fcntl
    from customer_qa_clone_access import clone_database_access
    from manage_management import query
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not output.exists() and digest(Path(__file__).resolve()) == helper_sha
        assert digest(package) == package_sha and digest(Path(target['config'])) == config_sha, 'Concurrent package or service configuration change'
        assert json.loads((stage/'qa_passed.json').read_text()) == proof
        verify_files(first_addons if args.live else stage/'addons', release)
        if args.live:
            assert json.loads((args.backup/'deployment.json').read_text()) == deployment
            validate_backup(args.environment, args.backup, deployment, package_sha, first_addons)
            validate_all_copies(stage.parent, package_sha, helper_sha, release)
        access = clone_database_access(query, database, stage, existing=True) if args.environment == 'qa-cerro' and not args.live else nullcontext()
        with access:
            header = 'import json\nPLAN=json.loads('+repr(json.dumps(plan))+')\n'
            result = subprocess.run(command, input=header+SCRIPT, text=True, capture_output=True)
        log = stage / ('harvest-default-job-' + mode + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.log')
        with log.open('x', encoding='utf-8') as stream:
            stream.write(result.stdout + result.stderr)
        log.chmod(0o600)
        assert result.returncode == 0, 'Native configuration failed; inspect private log '+str(log)
        lines = [line[len(MARKER):] for line in result.stdout.splitlines() if line.startswith(MARKER)]
        assert len(lines) == 1, 'The native configuration did not confirm its transaction'
        evidence = json.loads(lines[0])
        evidence['created_at'] = datetime.now(timezone.utc).isoformat()
        with output.open('x', encoding='utf-8') as stream:
            json.dump(evidence, stream, indent=2)
        output.chmod(0o600)
    print('HARVEST_DEFAULT_JOB_OK '+json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    main()
