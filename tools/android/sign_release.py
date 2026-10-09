"""Sign locally; never send the upload key or its password to CI or Git."""
import argparse
import hashlib
import json
import secrets
import subprocess
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jdk', type=Path, required=True)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--private', type=Path, required=True)
    p.add_argument('--build-number', type=int, required=True)
    a = p.parse_args()
    a.private.mkdir(parents=True, exist_ok=True)
    key = a.private/'steps-upload.p12'; password = a.private/'password.txt'
    if not key.exists():
        assert not password.exists(), 'Partial key creation: inspect private directory'
        password.write_text(secrets.token_urlsafe(48), encoding='utf-8')
        subprocess.run([str(a.jdk/'bin/keytool.exe'), '-genkeypair', '-keystore', str(key),
            '-storetype', 'PKCS12', '-alias', 'steps-upload', '-keyalg', 'RSA', '-keysize', '3072',
            '-validity', '10000', '-dname', 'CN=Steps App, C=CL', '-storepass:file', str(password),
            '-keypass:file', str(password)], check=True)
    assert password.exists()
    bundle = next(a.build.rglob('app-release.aab'))
    apk = next(a.build.rglob('app-release-unsigned.apk'))
    signer = next(a.build.rglob('apksigner.jar'))
    out = a.private.parent/'signed'; out.mkdir(exist_ok=True)
    signed_bundle = out/f'Steps-App-{a.build_number}.aab'; signed_apk = out/f'Steps-App-{a.build_number}.apk'
    subprocess.run([str(a.jdk/'bin/jarsigner.exe'), '-keystore', str(key), '-storepass:file', str(password),
        '-keypass:file', str(password), '-signedjar', str(signed_bundle), str(bundle), 'steps-upload'], check=True)
    subprocess.run([str(a.jdk/'bin/jarsigner.exe'), '-verify', str(signed_bundle)], check=True)
    subprocess.run([str(a.jdk/'bin/java.exe'), '-jar', str(signer), 'sign', '--ks', str(key),
        '--ks-key-alias','steps-upload', '--ks-pass','file:'+str(password),
        '--out', str(signed_apk), str(apk)], check=True)
    subprocess.run([str(a.jdk/'bin/java.exe'), '-jar', str(signer), 'verify', '--verbose', '--print-certs', str(signed_apk)], check=True)
    proof = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (signed_bundle,signed_apk)}
    (out/'sha256.json').write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof))

if __name__ == '__main__': main()
