"""Install and prove only free Studio providers on the restored Cerro library trial."""
import argparse
import ast
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

from restore_cerro_studio_strict import ROOT, TARGET, module_census, sql

RUNTIME = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
ANCHOR = Path('/srv/odoo-data/steps-anchor-validation/community-original-handover-20261126U40D')
LIBRARY = Path('/opt/steps-validation/community-historical-library-20261126U41L')
LIBRARY_PACKAGES = {
    '18.0.1.0.4': ('proof-fd485cda0d27', '0c5131e2cbdfab81bc161ec234822ebee89d34f6c79c7203ebc39880bb0f4426'),
    '18.0.1.0.5': ('proof-f8ffbc336c51', 'a5da5d753c098a23ffda43c7344c01c08419f26fd6193d0975d8a65e41148db4'),
}
PARENT_PROFILE = 'agriculture-parents-b08f02345e59'
PARENT_HASHES = {
    'step_cerro_studio_species': 'e0ebfd91c02e3d08430ed8da4cab2dcf5a2a79359d984cc5fd5ef1326a95a07b',
    'step_cerro_studio_agriculture': '521a2f809b821c9c0750b5aa39a364a39b055990055e828eebf886b0a086a2fe',
}
CORE_SCOPE = 'core-scope-2aacc0a97940'
CORE_SHA = 'c033b2fa4a1c45072abeb1707eba9cd672167d300707bd0d02981654870258db'
PROCESS_PROFILE = 'process-catalog-4f7fbac81c90'
PROCESS_HASHES = {
    'step_packing_process_catalog': '2cde86f902761b8dd9a19696b8f5d18b7cad68c540536c0162b03041e93282be',
    'step_packing_process_category': '0905d010a276a64f681fc992cea56697c9a415028e3ce5d64ed18fb5842e26a5',
    'step_cerro_studio_process_types': 'bdc304f35307ffe4d1c598875972259da97f0cc947497e55d2dbedd7308f4ef8',
}
MODULES = ('step_cerro_studio_farms', 'step_cerro_product_account_views', 'step_cerro_studio_agriculture', 'step_cerro_studio_companies',
           'step_cerro_studio_budgets', 'step_cerro_studio_producers', 'step_cerro_studio_species',
           'step_cerro_studio_process_types', 'step_cerro_studio_transfers', 'step_cerro_studio_packing',
           'step_cerro_studio_exports', 'step_cerro_bom_company')
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


def document_library(database):
    version = sql(database, "SELECT latest_version FROM ir_module_module WHERE name='step_document_library' AND state='installed'")
    if version not in LIBRARY_PACKAGES:
        raise ValueError('The restored library version has no independently admitted source package')
    directory, sha = LIBRARY_PACKAGES[version]
    return LIBRARY / directory, sha


def validate_modules(roots, database=TARGET):
    seal = json.loads((ROOT / 'module-content-v4.json').read_text())
    library, archive_sha = document_library(database)
    library_archive = library / 'package.tar'
    if hashlib.sha256(library_archive.read_bytes()).hexdigest() != archive_sha:
        raise ValueError('The admitted document library package changed')
    library_module = library / 'addons/step_document_library'
    with tarfile.open(library_archive) as archive:
        members = {m.name: m for m in archive.getmembers() if m.isfile() and m.name.startswith('addons/step_document_library/')}
        files = {f.relative_to(library).as_posix(): f for f in library_module.rglob('*')
                 if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'}
        if files.keys() != members.keys() or any(path.read_bytes() != archive.extractfile(members[name]).read()
                                                 for name, path in files.items()):
            raise ValueError('The document library sources do not match the admitted package')
    parent = ROOT / PARENT_PROFILE
    if {p.name: tree_sha(p) for p in parent.iterdir() if p.is_dir()} != PARENT_HASHES:
        raise ValueError('The agricultural view providers changed')
    if tree_sha(ROOT / CORE_SCOPE / 'step_agriculture_core') != CORE_SHA:
        raise ValueError('The admitted core identity set changed')
    process = ROOT / PROCESS_PROFILE
    if {p.name: tree_sha(p) for p in process.iterdir() if p.is_dir()} != PROCESS_HASHES:
        raise ValueError('The packing process catalogue package changed')
    consumed = set()
    private_sources = {}
    recorded = json.loads(sql(database, """SELECT coalesce(json_object_agg(name,latest_version),'{}')
                                         FROM ir_module_module WHERE state='installed'"""))
    for root in roots[:-2]:
        for module in root.iterdir():
            manifest = module / '__manifest__.py'
            if not manifest.exists() or module.name in consumed:
                continue
            consumed.add(module.name)
            spec = ast.literal_eval(manifest.read_text())
            license_name = spec.get('license')
            if license_name is None and module.name == 'l10n_cl_communes':
                # The pinned source omits the key. Odoo assigns LGPL-3 in its manifest
                # loader and the original Cerro catalogue records exactly this value.
                license_name = sql(database, "SELECT license FROM ir_module_module WHERE name='l10n_cl_communes'")
                if license_name != 'LGPL-3':
                    raise ValueError('The recorded license for Comunas differs from its Odoo manifest default')
            if license_name not in FREE:
                raise ValueError('Private non-free source: ' + module.name)
            if module.name in recorded and recorded[module.name]:
                v = spec.get('version', '1.0')
                v = v if v.startswith('18.0.') else '18.0.' + v
                if tuple(map(int, v.split('.'))) < tuple(map(int, recorded[module.name].split('.'))):
                    raise ValueError('Private provider version downgrade: ' + module.name)
            digest = tree_sha(module)
            if root.name in seal and digest != seal[root.name][module.name]:
                raise ValueError('Private provider source changed: ' + module.name)
            private_sources[str(module)] = digest
    verify = '''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from check_cerro_studio_strict import tree_sha
for name, expected in json.load(sys.stdin).items():
    module = Path(name)
    if not (module / '__manifest__.py').is_file() or tree_sha(module) != expected:
        raise ValueError("Odoo cannot read every admitted source file in " + str(module))
'''
    subprocess.run(['runuser', '-u', 'odoo', '--', '/usr/bin/python3.10', '-c', verify,
                    str(ROOT / 'tools')], input=json.dumps(private_sources), text=True, check=True)


def addon_roots(database=TARGET):
    library, _ = document_library(database)
    return [ROOT / CORE_SCOPE, ROOT / PROCESS_PROFILE, ROOT / PARENT_PROFILE, ROOT / 'directory-views', ROOT / 'directory-d20e40fe40f8', ROOT / 'view-alias-add2d259eb',
            ROOT / 'alias-8223860c89e8', ROOT / 'owners', ROOT / 'operators', library / 'addons',
            ANCHOR / 'runtime-addons', ANCHOR / 'engine-addons', RUNTIME / 'addons', RUNTIME / 'odoo/addons']


def missing_providers(module):
    installed = set(sql(TARGET, "SELECT name FROM ir_module_module WHERE state='installed'").splitlines())
    roots = addon_roots()
    remaining = [module]
    wanted = set()
    while remaining:
        name = remaining.pop()
        if name in installed or name in wanted:
            continue
        wanted.add(name)
        path = next((r / name / '__manifest__.py' for r in roots if (r / name / '__manifest__.py').is_file()), None)
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


def run(phase, extra, payload=None, *, database=TARGET, directory=ROOT, roots=None):
    roots = roots or addon_roots(database)
    validate_modules(roots, database)
    pre = ['unshare', '--net', '--', 'runuser', '-u', 'odoo', '--', 'env', 'PYTHONDONTWRITEBYTECODE=1',
           '/usr/bin/python3.10', str(RUNTIME / 'odoo-bin')]
    args = ['-c', '/etc/dev_odoo18.conf', '-d', database, '--db-filter=^' + database + '$',
            '--db_host=/var/run/postgresql', '--addons-path=' + ','.join(map(str, roots)),
            '--data-dir=' + str(directory / 'data'), '--logfile=' + str(directory / 'data/strict-odoo.log'),
            '--no-http', '--workers=0', '--max-cron-threads=0', '--load=base,web', '--stop-after-init', '--without-demo=all']
    logfile = directory / (phase + '.log')
    with logfile.open('wb') as out:
        subprocess.run(pre + (['shell'] if payload else []) + args + extra, check=True,
                       input=payload.encode() if payload else None, stdout=out, stderr=subprocess.STDOUT)


def main(phase, selected=None):
    if selected and (phase != 'install' or selected not in MODULES):
        raise ValueError('Choose a declared view provider to install')
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
evidence = dict(farm=capture(env),rights=exercise(env),directory=directory(env),view=render(env,actor,row))
print('CERRO_STRICT_FARMS_USER', json.dumps(evidence, sort_keys=True), flush=True)
evidence['aliases'] = legacy_aliases(env)
print('CERRO_STRICT_FARMS', json.dumps(evidence,sort_keys=True))'''
        elif phase == 'install':
            # Each group has independent application data. The first failed
            # transaction cannot conceal a valid result for another group.
            failures = []
            blocked = {}
            for module in ((selected,) if selected else MODULES):
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
from probe_cerro_process_category import capture as processes
from probe_cerro_species_pallet import capture as species_rows
species = None
if env.ref('step_cerro_studio_species.species', raise_if_not_found=False):
    try:
        with env.cr.savepoint():
            species = species_rows(env, test=True)
    except Exception as error:
        species = {'error': type(error).__name__, 'detail': str(error)[:240]}
process = None
if env.ref('step_cerro_studio_process_types.process_types', raise_if_not_found=False):
    try:
        with env.cr.savepoint():
            process = processes(env, test=True)
    except Exception as error:
        process = {'error': type(error).__name__, 'detail': str(error)[:240]}
print('CERRO_STRICT_VIEWS',json.dumps(dict(views=capture(env),routes=routes(env),screens=inspect(env),fullread=fullread(env),process=process,species=species),sort_keys=True))'''
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
    parser.add_argument('--module', choices=MODULES)
    args = parser.parse_args()
    main(args.phase, args.module)
