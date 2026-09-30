import base64
import hashlib
import hmac
import json
import time


def sign_identity(database, company_id, user_id, role, key):
    stamp = int(time.time())
    data = {'iss': database, 'aud': 'steps-tracker-v1', 'sub': str(user_id),
            'iat': stamp, 'exp': stamp+60, 'company_id': company_id, 'role': role}
    encode = lambda obj: base64.urlsafe_b64encode(json.dumps(obj, separators=(',', ':')).encode()).rstrip(b'=')
    message = encode({'alg': 'HS256', 'typ': 'JWT'}) + b'.' + encode(data)
    return (message+b'.'+base64.urlsafe_b64encode(hmac.new(key.encode(), message, hashlib.sha256).digest()).rstrip(b'=')).decode()
