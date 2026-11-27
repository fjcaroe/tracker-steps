"""Install and prove only free Studio providers on the restored Cerro library trial."""
import argparse
import ast
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess

from restore_cerro_studio_strict import ROOT, TARGET, module_census, sql

RUNTIME = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
ANCHOR = Path('/srv/odoo-data/steps-anchor-validation/community-original-handover-20261126U40D')
LIBRARY = Path('/opt/steps-validation/community-historical-library-20261126U41L')
MODULES = ('step_cerro_studio_farms', 'step_cerro_product_account_views', 'step_cerro_studio_agriculture', 'step_cerro_studio_companies',
           'step_cerro_studio_budgets', 'step_cerro_studio_producers', 'step_cerro_studio_species',
           'step_cerro_studio_process_types', 'step_cerro_studio_transfers')
FREE = {'AGPL-3', 'LGPL-3', 'GPL-3', 'GPL-2', 'GPL-3 or any later version', 'GPL-2 or any later version'}


def tree_sha(module):
    digest = hashlib.sha256()
    for f in sorted(module.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts or f.suffix == '.pyc':
            continue
        name = f.relative_to(module).as_posix().encode()
        content = hashlib.sha256(f.read_bytes()).digest()
        digest.update(len(name).to_bytes(4, 'big') + name + content)
    return digest.hexdigest()


def validate_modules(roots):
    seal = json.loads((ROOT / 'module-content-v4.json').read_text())
    consumed = set()
    recorded = json.loads(sql(TARGET, """SELECT coalesce(json_object_agg(name,latest_version),'{}')
                                         FROM ir_module_module WHERE state='installed'"""))
    for root in roots[:-2]:
        for module in root.iterdir():
            manifest = module / '__manifest__.py'
            if not manifest.exists() or module.name in consumed:
                continue
            consumed.add(module.name)
            spec = ast.literal_eval(manifest.read_text())
            if spec.get('license') not in FREE:
                raise ValueError('Private non-free source: ' + module.name)
            if module.name in recorded and recorded[module.name]:
                v = spec.get('version', '1.0')
                v = v if v.startswith('18.0.') else '18.0.' + v
                if tuple(map(int, v.split('.'))) < tuple(map(int, recorded[module.name].split('.'))):
                    raise ValueError('Private provider version downgrade: ' + module.name)
            if root.name in seal and tree_sha(module) != seal[root.name][module.name]:
                raise ValueError('Private provider source changed: ' + module.name)


def addon_roots():
    return [ROOT / 'directory-views', ROOT / 'directory-d20e40fe40f8', ROOT / 'view-alias-add2d259eb',
            ROOT / 'alias-8223860c89e8', ROOT / 'owners', ROOT / 'operators', LIBRARY / 'addons',
            ANCHOR / 'runtime-addons', ANCHOR / 'engine-addons', RUNTIME / 'addons', RUNTIME / 'odoo/addons']


def missing_providers(module):
    installed = set(sql(TARGET, "SELECT name FROM ir_module_module WHERE state='installed'").splitlines())
    remaining = [module]
    wanted = set()
    while remaining:
        name = remaining.pop()
        if name in installed or name in wanted:
            continue
        wanted.add(name)
        path = next((r / name / '__manifest__.py' for r in addon_roots() if (r / name / '__manifest__.py').is_file()), None)
        if not path:
            return wanted, 'Fuente ausente: ' + name
        spec = ast.literal_eval(path.read_text())
        if spec.get('license','LGPL-3') not in FREE:
            return wanted, 'Fuente sin licencia libre: ' + name
        remaining.extend(spec.get('depends', []))
    return wanted, None


def incompatible_contracts(module):
    wanted, error = missing_providers(module)
    if error:
        return [error]
    out = []
    if 'step_management_costs' in wanted:
        unique = sql(TARGET, """SELECT pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE conrelid='step_management_estimation_line'::regclass
                    AND conname='step_management_estimation_line_estimation_line_center_unique'""")
        if unique == 'UNIQUE (estimation_id, center_id, cuartel_id)':
            out.append('step_management_costs exige unicidad por estimación/centro antes de cargar los cuarteles')
    if 'step_packing' in wanted:
        master = sql(TARGET, """SELECT c.confrelid::regclass::text FROM pg_constraint c
                    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
                    WHERE c.contype='f' AND c.conrelid='step_packing_picking_tag_line'::regclass
                    AND a.attname='category_id'""")
        if master == 'step_management_fruit_category':
            out.append('step_packing declara la categoría retirada antes de cargar el catálogo unificado')
    return out


def run(phase, extra, payload=None):
    roots = addon_roots()
    validate_modules(roots)
    pre = ['unshare', '--net', '--', 'runuser', '-u', 'odoo', '--', 'env', 'PYTHONDONTWRITEBYTECODE=1',
           '/usr/bin/python3.10', str(RUNTIME / 'odoo-bin')]
    args = ['-c', '/etc/dev_odoo18.conf', '-d', TARGET, '--db-filter=^' + TARGET + '$',
            '--db_host=/var/run/postgresql', '--addons-path=' + ','.join(map(str, roots)),
            '--data-dir=' + str(ROOT / 'data'), '--logfile=' + str(ROOT / 'data/strict-odoo.log'),
            '--no-http', '--workers=0', '--max-cron-threads=0', '--load=base,web', '--stop-after-init', '--without-demo=all']
    logfile = ROOT / (phase + '.log')
    with logfile.open('wb') as out:
        subprocess.run(pre + (['shell'] if payload else []) + args + extra, check=True,
                       input=payload.encode() if payload else None, stdout=out, stderr=subprocess.STDOUT)


def main(phase):
    with open('/run/lock/steps-environments.lock', 'rb') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        receipt = json.loads((ROOT / 'clone-receipt.json').read_text())
        assert receipt['target'] == TARGET
        before = module_census(TARGET)
        assert not any(before[n] for n in ('non_free', 'enterprise', 'pending')) and before['fundos'] == 1
        if phase == 'fundos':
            body = '''from probe_cerro_shared_farms import capture, exercise
from probe_cerro_studio_views import inventory, render
from probe_cerro_legacy_aliases import capture as legacy_aliases
from probe_cerro_farm_directory import capture as directory
actor = env['res.users'].browse(6)
row = next(row for row in inventory(env).values() if row['model']=='step.fundo')
print('CERRO_STRICT_FARMS', json.dumps(dict(farm=capture(env),rights=exercise(env),directory=directory(env),view=render(env,actor,row),aliases=legacy_aliases(env)),sort_keys=True))'''
        elif phase == 'install':
            # Each group has independent application data. The first failed
            # transaction cannot conceal a valid result for another group.
            failures = []
            blocked = {}
            for module in MODULES:
                state = sql(TARGET, "SELECT state FROM ir_module_module WHERE name='" + module + "'")
                if state == 'installed':
                    continue
                reasons = incompatible_contracts(module)
                if reasons:
                    blocked[module] = reasons
                    continue
                try:
                    run('install-' + module, ['-i', module])
                    if sql(TARGET, "SELECT state FROM ir_module_module WHERE name='" + module + "'") != 'installed':
                        raise ValueError('The module was not installed')
                except (ValueError, subprocess.CalledProcessError):
                    failures.append(module)
                after = module_census(TARGET)
                assert not any(after[n] for n in ('non_free', 'enterprise', 'pending'))
            print(json.dumps({'failed_modules': failures, 'blocked_modules': blocked, 'state': module_census(TARGET)}, sort_keys=True))
            return
        else:
            body = '''from probe_cerro_studio_client import capture
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_screen import inspect
from probe_cerro_studio_fullread import capture as fullread
print('CERRO_STRICT_VIEWS',json.dumps(dict(views=capture(env),routes=routes(env),screens=inspect(env),fullread=fullread(env)),sort_keys=True))'''
        payload = 'import json,sys\nsys.path.insert(0,' + repr(str(ROOT / 'tools')) + ')\n' + body + '\nenv.cr.rollback()\n'
        run(phase, [], payload)
        after = module_census(TARGET)
        assert before == after
        result = (ROOT / (phase + '.log')).read_text()
        expected = 'CERRO_STRICT_FARMS ' if phase == 'fundos' else 'CERRO_STRICT_VIEWS '
        if not any(l.startswith(expected) for l in result.splitlines()):
            raise ValueError('The registry did not emit a successful receipt')
        print(json.dumps({'phase': phase, 'state': after}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('fundos', 'install', 'views'), required=True)
    main(parser.parse_args().phase)
