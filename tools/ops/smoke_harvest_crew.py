"""Exercise enrollment and attendance only through a certified Harvest .8 copy.

Creates one clearly marked QA employee and native attendance inside the private
destination copy. No credentials, session IDs or published hosts are accepted.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import uuid
from zoneinfo import ZoneInfo

from smoke_harvest_android_sync import ReviewClient, positive_id, require_success, review_origin


class CrewClient(ReviewClient):
    allowed_requests = (('GET', '/api/harvest/session'), ('GET', '/api/harvest/bootstrap'),
                        ('GET', '/api/harvest/ref/jobs'), ('POST', '/api/harvest/crew/sync'))


def validate_crew_policy(origin, stage_name, proof, policy):
    origin = review_origin(origin)
    environment = policy['environment']
    assert environment in ('development', 'cerro', 'qa-cerro')
    assert proof['environment'] == environment
    frontend = policy['harvest_web']
    assert frontend['repository'] == 'stepconsulting/step_harvest' and frontend['version'] == '0.0.8'
    assert re.fullmatch('[a-f0-9]{40}', frontend['commit'])
    assert re.fullmatch('[a-f0-9]{40}', proof['commit'])
    assert re.fullmatch('[a-f0-9]{64}', proof['release_sha256'])
    run_id = 't236237_' + proof['commit'][:8]
    assert stage_name == 'management_' + environment + '_' + run_id
    assert proof['database'] == 'MANAGEMENT_QA_' + environment.upper() + '_' + run_id
    assert proof['feature'] == 'harvest-app' and proof['business_preserved'] is True
    assert not proof.get('readonly_copy')
    assert policy['database'] == proof['database']
    assert policy['web_commit'] == frontend['commit']
    assert policy['read_only'] is False and policy['copy_sync_allowed'] is True
    assert policy['sync_origin'] == origin
    assert positive_id(policy['user_id']) and policy['user_id'] > 1
    assert positive_id(policy['company_id'])


def exercise_crew(client, policy, timezone_name, run_uuid=None):
    status, session = client.request('GET', '/api/harvest/session')
    require_success(status, session, 'Native session')
    assert session.get('connected') is True
    status, bootstrap = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, bootstrap, 'Native bootstrap')
    for value in (session, bootstrap):
        assert value['user']['id'] == policy['user_id']
        assert value['company']['id'] == policy['company_id']
    scope = bootstrap['scope']
    assert isinstance(scope, str) and re.fullmatch('[a-f0-9]{64}', scope) and session['scope'] == scope
    assert bootstrap['crew_permissions']['enroll'] is True and bootstrap['crew_permissions']['attendance'] is True
    status, jobs = client.request('GET', '/api/harvest/ref/jobs')
    require_success(status, jobs, 'Native job catalog')
    assert isinstance(jobs.get('items'), list) and all(positive_id(row['id']) for row in jobs['items'])
    crews = [row for row in bootstrap['crews'] if positive_id(row.get('id'))
             and row.get('type') in ('propio', 'contratista')
             and (row['type'] == 'propio' or positive_id((row.get('contractor') or {}).get('id')))]
    assert crews, 'The selected copy company needs an existing compatible native crew'
    crew = next((row for row in crews if row['type'] == 'propio'), crews[0])
    previous_members = set(crew.get('worker_ids', []))
    run_uuid = run_uuid or 'QA-HARVEST-CREW-' + uuid.uuid4().hex
    assert re.fullmatch(r'QA-HARVEST-CREW-[a-f0-9]{32}', run_uuid)
    pin = str(97000000 + int(run_uuid[-6:], 16) % 1000000)
    worker = {'client_uuid': run_uuid, 'crew_id': crew['id'], 'name': 'QA Harvest worker ' + run_uuid[-12:],
              'nip': pin, 'sex': 'F', 'job_id': None}
    altered = ('f' if scope[0] != 'f' else 'e') + scope[1:]
    status, rejected = client.request('POST', '/api/harvest/crew/sync',
                                      {'scope': altered, 'workers': [worker], 'attendances': []})
    assert status == 409 and rejected.get('ok') is False

    def enroll():
        status, result = client.request('POST', '/api/harvest/crew/sync',
                                       {'scope': scope, 'workers': [worker], 'attendances': []})
        require_success(status, result, 'Copy enrollment')
        rows = result['worker_results']
        assert len(rows) == 1 and rows[0]['ok'] is True and rows[0]['client_uuid'] == run_uuid
        assert positive_id(rows[0].get('id')) and result['attendance_results'] == []
        return rows[0]['id']

    worker_id = enroll()
    assert enroll() == worker_id, 'Enrollment retry created another native employee'
    user_timezone = timezone.utc if timezone_name == 'UTC' else ZoneInfo(timezone_name)
    date = datetime.now(user_timezone).date()
    start = datetime.combine(date, datetime.min.time(), tzinfo=user_timezone).replace(hour=8)
    end = start + timedelta(hours=8)
    attendance = {'client_uuid': run_uuid + '-ATTENDANCE', 'crew_id': crew['id'], 'date': date.isoformat(),
                  'entries': [{'worker_uuid': run_uuid, 'check_in': start.isoformat(), 'check_out': end.isoformat()}]}

    def attend(values, success=True):
        status, result = client.request('POST', '/api/harvest/crew/sync',
                                       {'scope': scope, 'workers': [], 'attendances': [values]})
        assert status == 200 and result['ok'] is success
        rows = result['attendance_results']
        assert len(rows) == 1 and rows[0]['ok'] is success and result['worker_results'] == []
        assert rows[0]['client_uuid'] == values['client_uuid']
        if success:
            assert len(rows[0]['id']) == 1 and positive_id(rows[0]['id'][0])
            return rows[0]['id'][0]
        assert rows[0].get('error') and not rows[0].get('id')

    attendance_id = attend(attendance)
    assert attend(attendance) == attendance_id, 'Attendance retry created another native attendance'
    changed = deepcopy(attendance)
    changed['entries'][0]['check_out'] = (end + timedelta(hours=1)).isoformat()
    attend(changed, success=False)
    wrong_day = dict(attendance, client_uuid=run_uuid + '-WRONG-DATE', date=(date + timedelta(days=1)).isoformat())
    attend(wrong_day, success=False)
    assert attend(attendance) == attendance_id
    status, refreshed = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, refreshed, 'Native refresh')
    assert refreshed['scope'] == scope
    employee = next(row for row in refreshed['workers'] if row['id'] == worker_id)
    assert employee['nip'] == pin and employee['sex'] == 'F' and positive_id(employee['job_id'])
    assert employee['job'].casefold() == 'cosechero'
    native_crew = next(row for row in refreshed['crews'] if row['id'] == crew['id'])
    assert previous_members.issubset(set(native_crew['worker_ids'])) and worker_id in native_crew['worker_ids']
    summary = next(row for row in refreshed['crew_attendance'] if row['crew_id'] == crew['id'] and row['date'] == date.isoformat())
    assert worker_id in summary['worker_ids']
    return {'run_uuid': run_uuid, 'native_worker_id': worker_id, 'native_crew_id': crew['id'], 'native_job_id': employee['job_id'],
            'native_attendance_id': attendance_id, 'worker_enrollment': True, 'crew_attendance': True,
            'attendance_home_total': True, 'native_members_preserved': True, 'native_job_default': True,
            'scope_rejected_before_write': True, 'enrollment_idempotency': True, 'attendance_idempotency': True,
            'changed_hours_rejected': True, 'wrong_date_rejected': True, 'native_context': True,
            'credentials_or_session_ids_supplied': False, 'new_workers': 1, 'new_attendances': 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--timezone', required=True, help='Existing review user timezone; never changes the profile')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    origin = review_origin(args.url)
    stage = args.stage
    assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation') and not stage.is_symlink()
    proof = json.loads((stage/'qa_passed.json').read_text())
    policy = json.loads((stage/'harvest-review-policy.json').read_text())
    validate_crew_policy(origin, stage.name, proof, policy)
    output = args.output
    assert output.is_absolute() and output.resolve() == output and not output.exists()
    assert not any((parent/'.git').exists() for parent in output.parents)
    evidence = exercise_crew(CrewClient(origin), policy, args.timezone)
    evidence.update({'feature': proof['feature'], 'stage': stage.name, 'database': proof['database'],
                     'web_commit': policy['harvest_web']['commit'], 'backend_commit': proof['commit'],
                     'company_id': policy['company_id'], 'user_id': policy['user_id'],
                     'backend_sha256': proof['release_sha256'], 'created_at': datetime.now(timezone.utc).isoformat()})
    configuration_path = stage/'harvest-default-job-copy.json'
    if configuration_path.is_file():
        from configure_harvest_default_job import bind_configuration_smoke, digest
        evidence = bind_configuration_smoke(evidence, json.loads(configuration_path.read_text()),
                                            policy['environment'], proof['release_sha256'],
                                            digest(Path(__file__).with_name('configure_harvest_default_job.py')))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    output.chmod(0o600)
    print('HARVEST_CREW_COPY_OK ' + json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    main()
