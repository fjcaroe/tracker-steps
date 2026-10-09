"""Install and launch the compiled beta on an ephemeral CI iPhone simulator.
This checks installation/launch and saves UI evidence; it does not certify GPS,
Keychain durability, Watch pairing or a physical-device signing profile.
"""
import json
import subprocess
import sys
import time


def sim(*args):
    return subprocess.check_output(['xcrun', 'simctl', *args], text=True, timeout=180).strip()


app, screenshot = sys.argv[1:]
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphonesimulator', '--show-sdk-version'], text=True, timeout=30).strip()
runtimes = [r for r in json.loads(sim('list', 'runtimes', '--json'))['runtimes']
            if r.get('isAvailable') and '.iOS-' in r['identifier'] and r['version'].split('.')[0] == sdk.split('.')[0]]
if not runtimes:
    raise SystemExit('No available iOS simulator runtime')
runtime = next((r for r in runtimes if r['version'] == sdk), sorted(runtimes, key=lambda r: tuple(int(v) for v in r['version'].split('.')))[-1])
device = sim('create', 'Steps beta smoke', 'com.apple.CoreSimulator.SimDeviceType.iPhone-16', runtime['identifier'])
try:
    sim('boot', device)
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
    subprocess.run(['xcrun', 'simctl', 'delete', device], check=False, timeout=30)
