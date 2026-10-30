"""Private HANDOVER/REFERENCE review SQL, with PostgreSQL readonly after sudo.

No connection credentials, service definitions, password file, interactive
prompt or psql startup file. Original trusted SELECT text is delegated intact.
This executor neither loads Odoo nor changes results or database state.
"""
import hashlib
import json
import re
import subprocess


DATABASE = r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+'
SETTING_QUERY = ("SELECT json_build_object('database',current_database(),"
    "'transaction_read_only',current_setting('transaction_read_only'),"
    "'default_transaction_read_only',current_setting('default_transaction_read_only'))")


def require(value, code):
    if not value:
        raise ValueError(code)


def command(database):
    require(isinstance(database, str) and re.fullmatch(
        r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_(?:HANDOVER|REFERENCE)_[A-Za-z0-9_]+', database),
        'private-review-command-database-required')
    # env -i occurs AFTER sudo. HOME has no real user's .pgpass; explicitly
    # fixing PGPASSFILE=/dev/null also prevents any home-file fallback.
    return ['/usr/bin/sudo', '-n', '-u', 'postgres', '/usr/bin/env', '-i',
        'PATH=/usr/bin:/bin', 'HOME=/nonexistent', 'PGHOST=/var/run/postgresql',
        'PGPASSFILE=/dev/null', 'PGSERVICEFILE=/dev/null',
        'PGOPTIONS=-c default_transaction_read_only=on',
        '/usr/bin/psql', '-X', '--no-password', '-q', '-v', 'ON_ERROR_STOP=1',
        '--host=/var/run/postgresql', '--username=postgres', '--dbname=' + database, '-At']


def admit_statement(statement):
    require(isinstance(statement, str) and statement.strip(), 'trusted-review-query-required')
    stripped = statement.strip()
    if stripped.startswith('SET jit=off; '):
        stripped = stripped[len('SET jit=off; '):]
    require(stripped.upper().startswith('SELECT '), 'select-only-original-review-required')
    # Inspect commands outside single-quoted literals, without evaluating SQL.
    # Existing trusted helpers use ordinary/E string literals and no comments
    # or dollar bodies. Reject unfamiliar syntax instead of widening the API.
    literals_removed = re.sub(r"'(?:''|[^'])*'", "''", stripped)
    require(not any(token in literals_removed for token in (';', '--', '/*', '*/', '$')),
        'review-multistatement-or-unreviewed-syntax')
    words = set(re.findall(r'[a-z_][a-z_0-9]*', literals_removed.lower()))
    require(not words.intersection({'insert', 'update', 'delete', 'create', 'alter', 'drop',
        'truncate', 'grant', 'revoke', 'commit', 'rollback', 'begin', 'call', 'copy', 'do',
        'nextval', 'setval', 'set_config', 'dblink', 'lo_import', 'lo_export'}),
        'review-write-session-counter-or-external-command')


class ReadOnlyReviewSQL:
    def __init__(self, database, reference):
        require(isinstance(database, str) and re.fullmatch(DATABASE, database)
            and reference == database.replace('_HANDOVER_', '_REFERENCE_'),
            'exact-private-handover-reference-pair-required')
        self.databases = (database, reference)
        self.settings = {}
        self.calls = []

    def _execute(self, database, statement):
        result = subprocess.run(command(database), input=statement, text=True, capture_output=True)
        # Never copy psql stderr into an exception: it may contain source SQL
        # or private values. The coordinator retains its own private logs.
        require(result.returncode == 0, 'readonly-postgresql-review-query-rejected')
        return result.stdout.strip()

    def __call__(self, database, statement):
        require(database in self.databases, 'review-query-outside-exact-private-pair')
        admit_statement(statement)
        if database not in self.settings:
            proof = json.loads(self._execute(database, SETTING_QUERY))
            require(proof == {'database': database, 'transaction_read_only': 'on',
                'default_transaction_read_only': 'on'}, 'actual-postgresql-readonly-setting-not-proven')
            self.settings[database] = proof
        output = self._execute(database, statement)
        self.calls.append({'database': database,
            'statement_sha256': hashlib.sha256(statement.encode()).hexdigest()})
        return output

    def proof(self):
        require(set(self.settings) == set(self.databases), 'both-private-databases-must-have-readonly-proof')
        return {'schema': 1, 'databases': list(self.databases), 'setting_queries': self.settings,
            'setting_query_sha256': hashlib.sha256(SETTING_QUERY.encode()).hexdigest(),
            'original_queries_delegated_unmodified': True, 'query_results_rewritten': False,
            'clean_environment_after_sudo': True, 'password_files_disabled': True,
            'interactive_password_prompt_disabled': True, 'psql_startup_files_disabled': True,
            'socket_only': True, 'query_count': len(self.calls), 'queries': self.calls}
