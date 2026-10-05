"""Check one complete key already present in the private value, without printing it."""
import json
import os
import re

import requests

from inspect_sys import process_environment


assert os.geteuid() == 0, 'Run as root'
value = process_environment('odoo18-demo-sys.service').get('OPENAI_API_KEY', '').strip()
matches = re.findall(r'sk-[A-Za-z0-9_-]{20,}', value)
assert len(matches) == 1, 'No unambiguous complete credential in the existing value'
candidate = matches[0]
response = requests.get('https://api.openai.com/v1/models',
                        headers={'Authorization': 'Bearer ' + candidate},
                        timeout=(5, 20), allow_redirects=False)
metadata = {'candidate_auth_status': response.status_code,
            'existing_value_has_extra_characters': candidate != value}
if response.status_code != 200:
    try:
        error = response.json().get('error', {})
        code = error.get('code')
        if isinstance(code, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', code):
            metadata['api_error_code'] = code
    except (ValueError, AttributeError):
        pass
print('EXISTING_KEY_PROBE ' + json.dumps(metadata))
