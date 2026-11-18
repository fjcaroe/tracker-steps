"""Install and launch the compiled beta on an ephemeral CI iPhone simulator.
This checks installation/launch and saves UI evidence; it does not certify GPS,
Keychain durability, Watch pairing or a physical-device signing profile.
"""
import json
import subprocess
import sys
import time


def sim(*args):
    print('simctl ' + ' '.join(args), flush=True)
    try:
        return subprocess.check_output(['xcrun', 'simctl', *args], text=True, timeout=180).strip()
    except subprocess.TimeoutExpired as error:
        if error.stdout:
            print(error.stdout.decode(errors='replace') if isinstance(error.stdout, bytes) else error.stdout, flush=True)
        raise


app, screenshot = sys.argv[1:]
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphonesimulator', '--show-sdk-version'], text=True, timeout=30).strip()
runtimes = [r for r in json.loads(sim('list', 'runtimes', '--json'))['runtimes']
            if r.get('isAvailable') and '.iOS-' in r['identifier'] and r['version'].split('.')[0] == sdk.split('.')[0]]
if not runtimes:
    raise SystemExit('No available iOS simulator runtime')
runtime = next((r for r in runtimes if r['version'] == sdk), sorted(runtimes, key=lambda r: tuple(int(v) for v in r['version'].split('.')))[-1])
devices = [d for d in json.loads(sim('list', 'devices', '--json'))['devices'].get(runtime['identifier'], []) if d.get('isAvailable') and d['name'].startswith('iPhone')]
existing = next((d for d in devices if d['state'] == 'Booted'), devices[0] if devices else None)
device = existing['udid'] if existing else sim('create', 'Steps beta smoke', 'com.apple.CoreSimulator.SimDeviceType.iPhone-16', runtime['identifier'])
try:
    subprocess.run(['open', '-g', '-a', 'Simulator', '--args', '-CurrentDeviceUDID', device], check=True, timeout=30)
    if not existing or existing['state'] != 'Booted':
        # The Simulator UI may already have started the requested device.
        subprocess.run(['xcrun', 'simctl', 'boot', device], check=False, timeout=30)
    sim('bootstatus', device, '-b')
    sim('install', device, app)
    result = sim('launch', device, 'cl.stepsapp.movil')
    if 'cl.stepsapp.movil:' not in result:
        raise RuntimeError('Simulator did not report an app process')
    # The embedded WebView loads local demonstration assets asynchronously.
    time.sleep(12)
    sim('io', device, 'screenshot', screenshot)
    print('iPhone simulator installed and launched Steps; screenshot saved.')
finally:
    subprocess.run(['xcrun', 'simctl', 'shutdown', device], check=False, timeout=30)
    if not existing:
        subprocess.run(['xcrun', 'simctl', 'delete', device], check=False, timeout=30)
