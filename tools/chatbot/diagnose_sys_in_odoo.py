"""Odoo shell input: classify API failures without logging keys, payloads or answers."""
import json
import re
from unittest.mock import patch

import requests

from odoo.addons.step_support_assistant.core import rank_sources


params = env['ir.config_parameter'].sudo()
for name, value in SOURCE_CONFIG.items():
    params.set_param('step_support_assistant.' + name, value)
user = env.ref('base.user_admin')
assistant = env['step.support.assistant'].with_user(user).sudo(False).with_context(
    allowed_company_ids=[user.company_id.id])
question = '¿Qué hago si no veo una aplicación o aparece acceso denegado?'
sources = rank_sources(question, assistant.env['step.assistant.article']._available_sources())
metadata = {'source_count': len(sources)}
original_post = requests.post


def observe_response(*args, **kwargs):
    response = original_post(*args, **kwargs)
    metadata['http_status'] = response.status_code
    try:
        payload = response.json()
    except ValueError:
        metadata['response_format'] = 'not_json'
        return response
    if isinstance(payload, dict):
        error = payload.get('error')
        if isinstance(error, dict):
            for field in ('code', 'type'):
                value = error.get(field)
                if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', value):
                    metadata['api_error_' + field] = value
        elif isinstance(payload.get('status'), str):
            metadata['response_status'] = payload['status'] if payload['status'] in {
                'completed', 'failed', 'incomplete', 'in_progress', 'queued', 'cancelled',
            } else 'unknown'
    return response


with patch('odoo.addons.step_support_assistant.models.assistant.requests.post', observe_response):
    try:
        result, usage = assistant._request(assistant._config(), question, [], sources)
        metadata['answer_status'] = result['status']
        metadata['verified_citations'] = len(result['sources'])
    except requests.RequestException as error:
        metadata['transport_error_class'] = type(error).__name__
    except (ValueError, KeyError, TypeError) as error:
        allowed = {'provider unavailable', 'invalid answer schema', 'invalid status',
                   'invalid answer', 'missing evidence', 'invalid citation', 'unknown citation',
                   'unsupported evidence', 'incomplete response'}
        metadata['validation_error'] = str(error) if str(error) in allowed else 'response_validation_failed'
env.cr.rollback()
print('SYS_API_DIAGNOSTIC ' + json.dumps(metadata))
