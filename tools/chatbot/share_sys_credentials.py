"""Reuse the existing demo-sys EnvironmentFile for SyS; never copy or print its key."""
import json
import os
from pathlib import Path
import shlex
import subprocess

from inspect_sys import process_environment


def main():
    assert os.geteuid() == 0, 'Run as root'
    source = Path('/etc/steps/assistant-demo-sys.env')
    assert source.is_file() and not source.is_symlink(), 'Missing private reference environment'
    metadata = source.stat()
    assert metadata.st_uid == 0 and metadata.st_mode & 0o777 == 0o600, 'Expected root-owned 0600 environment'
    variables = dict(item.split('=', 1) for item in
                     shlex.split(source.read_text(), comments=True) if '=' in item)
    runtime = process_environment('odoo18-demo-sys.service')
    key = runtime.get('OPENAI_API_KEY', '').strip()
    assert key and variables.get('OPENAI_API_KEY', '').strip() == key, 'Reference key must match its running service'
    # Sharing a file that contains unrelated credentials would broaden their access.
    assert set(variables) == {'OPENAI_API_KEY'}, 'Reference environment must contain only the API key'
    directory = Path('/etc/systemd/system/odoo18-sys.service.d')
    assert not directory.is_symlink(), 'Unexpected systemd directory'
    directory.mkdir(mode=0o755, exist_ok=True)
    destination = directory / 'steps-assistant.conf'
    content = '[Service]\nEnvironmentFile=/etc/steps/assistant-demo-sys.env\n'
    assert not destination.is_symlink(), 'Unexpected systemd override'
    if destination.exists():
        assert destination.read_text() == content, 'Existing override differs; review required'
    else:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, 'w') as output:
            output.write(content)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    print(json.dumps({'result': 'SHARED_EXISTING_CREDENTIAL_FILE',
                      'service': 'odoo18-sys.service', 'override': str(destination),
                      'source_environment': str(source), 'key_available': True}))


if __name__ == '__main__':
    main()
