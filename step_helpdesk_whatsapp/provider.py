"""Independent Cloud API transport. Never log a token, URL or provider body."""
import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit
import requests

MIME = {'image': {'image/jpeg', 'image/png'},
        'audio': {'audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr', 'audio/ogg'},
        'document': {'application/pdf', 'text/plain', 'application/msword',
                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                     'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}}


class ProviderError(Exception):
    def __init__(self, code, retry=False, uncertain=False):
        self.code, self.retry, self.uncertain = code, retry, uncertain
        super().__init__(code)


def signature_valid(raw, signature, secret):
    return bool(secret and re.fullmatch(r'sha256=[a-fA-F0-9]{64}', signature or '') and
        hmac.compare_digest(signature[7:].lower(), hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()))


def normalize(payload, account, phone):
    events = []
    for entry in payload.get('entry', []):
        if str(entry.get('id')) != account:
            raise ValueError('wrong_account')
        for change in entry.get('changes', []):
            value = change.get('value', {})
            if change.get('field') != 'messages':
                continue
            if str(value.get('metadata', {}).get('phone_number_id')) != phone:
                raise ValueError('wrong_phone')
            for message in value.get('messages', []):
                kind = message.get('type', 'unknown')
                if not message.get('id') or not message.get('from'):
                    raise ValueError('incomplete_message')
                content = message.get(kind, {})
                events.append({'kind':'incoming', 'external_id':message['id'], 'sender':message['from'],
                    'sender_phone':next(('+'+c['wa_id'] for c in value.get('contacts',[]) if c.get('wa_id')==message['from'] and re.fullmatch(r'\d{8,15}',c['wa_id'])),None),
                    'timestamp':message.get('timestamp'), 'type':kind,
                    'text':content.get('body', content.get('caption', '')),
                    'media_id':content.get('id'), 'mime':content.get('mime_type'), 'filename':content.get('filename'),
                    'reply_to':message.get('context', {}).get('id')})
            for status in value.get('statuses', []):
                if not status.get('id') or not status.get('status'):
                    raise ValueError('incomplete_status')
                events.append({'kind':'status', 'external_id':status['id'], 'status':status['status'],
                    'timestamp':status.get('timestamp'), 'sender':status.get('recipient_id'),
                    'local_id':status.get('biz_opaque_callback_data')})
    return events


def event_key(event):
    identity = [event.get('kind'), event.get('external_id')]
    if event.get('kind')!='incoming':
        identity.extend([event.get('status'),event.get('timestamp')])
    return hashlib.sha256(json.dumps(identity, separators=(',', ':')).encode()).hexdigest()


class MetaCloudProvider:
    def __init__(self, channel):
        if not re.fullmatch(r'v\d{1,2}\.0', channel.graph_version or ''):
            raise ProviderError('graph_version_missing')
        self.channel = channel
        self.base = 'https://graph.facebook.com/' + channel.graph_version

    def request(self, method, path, sending=False, **kwargs):
        try:
            response = requests.request(method, self.base + '/' + path,
                headers={'Authorization':'Bearer '+self.channel.access_token}, timeout=(10,30),
                allow_redirects=False, **kwargs)
        except requests.exceptions.RequestException:
            raise ProviderError('network_error', retry=not sending, uncertain=sending) from None
        if response.status_code == 429:
            raise ProviderError('rate_limited', retry=True)
        if not response.ok:
            raise ProviderError('provider_http_'+str(response.status_code), retry=response.status_code>=500 and not sending,
                uncertain=response.status_code>=500 and sending)
        try:
            result = response.json()
        except ValueError:
            raise ProviderError('invalid_provider_response', uncertain=sending) from None
        if not isinstance(result,dict):
            raise ProviderError('invalid_provider_response',uncertain=sending)
        if result.get('error'):
            raise ProviderError('provider_rejected')
        return result

    def send(self, message, media=None):
        payload = {'messaging_product':'whatsapp', 'to':message.conversation_id.sender_id,
            'type':message.kind, 'biz_opaque_callback_data':message.local_id}
        if message.kind == 'text':
            payload['text'] = {'body':message.text, 'preview_url':False}
        elif message.kind == 'template':
            payload['template'] = {'name':message.template_id.name, 'language':{'code':message.template_id.language}}
            if message.template_parameters:
                payload['template']['components']=[{'type':'body', 'parameters':[{'type':'text','text':str(p)} for p in message.template_parameters]}]
        else:
            attachment = message.attachment_id
            upload = self.request('POST', self.channel.phone_number_id+'/media',
                data={'messaging_product':'whatsapp'}, files={'file':(attachment.name, attachment.raw, attachment.mimetype)})
            if not upload.get('id'):
                raise ProviderError('media_upload_failed')
            payload[message.kind] = {'id':upload['id']}
            if message.kind == 'document':
                payload['document']['filename'] = attachment.name
        result = self.request('POST', self.channel.phone_number_id+'/messages', sending=True, json=payload)
        messages = result.get('messages', [])
        if not messages or not messages[0].get('id'):
            raise ProviderError('message_id_missing', uncertain=True)
        return messages[0]['id']

    def download(self, media_id, expected_mime):
        if not re.fullmatch(r'[\w.-]{1,200}', media_id or ''):
            raise ProviderError('invalid_media_id')
        meta = self.request('GET', media_id)
        if meta.get('mime_type') != expected_mime or int(meta.get('file_size',0)) > self.channel.max_media_mb*1024*1024:
            raise ProviderError('media_type_or_size')
        url = urlsplit(meta.get('url',''))
        if url.scheme!='https' or url.hostname not in ('lookaside.fbsbx.com','mmg.whatsapp.net','scontent.whatsapp.net') or url.username or url.password or url.port not in (None,443):
            raise ProviderError('unsafe_media_url')
        try:
            with requests.get(url.geturl(), headers={'Authorization':'Bearer '+self.channel.access_token},
                timeout=(10,30), stream=True, allow_redirects=False) as response:
                if not response.ok:
                    raise ProviderError('media_http_error', retry=True)
                data = bytearray()
                for part in response.iter_content(65536):
                    data.extend(part)
                    if len(data)>self.channel.max_media_mb*1024*1024:
                        raise ProviderError('media_too_large')
        except requests.exceptions.RequestException:
            raise ProviderError('media_network_error', retry=True) from None
        if meta.get('sha256') and hashlib.sha256(data).hexdigest()!=meta['sha256']:
            raise ProviderError('media_digest_mismatch')
        return bytes(data)

    def templates(self):
        return self.request('GET', self.channel.account_id+'/message_templates', params={'limit':100}).get('data', [])


class MockWhatsAppProvider:
    """No requests, no credentials, deterministic IDs. Failure tests patch send."""
    def __init__(self, channel):
        self.channel = channel

    def send(self, message, media=None):
        return 'mock.'+message.local_id

    def download(self, media_id, expected_mime):
        if expected_mime=='application/pdf':
            return b'%PDF-1.4\n% mock fixture\n%%EOF'
        if expected_mime=='audio/ogg':
            return b'OggS'+b'\0'*32
        raise ProviderError('mock_media_missing')

    def templates(self):
        return [{'name':'support_followup','language':'es','status':'APPROVED','category':'UTILITY'}]
