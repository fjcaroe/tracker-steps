"""Resolve each Cerro view package against the actual approved Community addon roots."""
import argparse
import json
from pathlib import Path
import re

FREE = {'LGPL-3', 'AGPL-3', 'GPL-3', 'GPL-2', 'GPL-3 or any later version', 'GPL-2 or any later version'}


def main():
    from odoo import sql_db
    from odoo.modules import module
    from odoo.modules.graph import Graph
    from odoo.tools import config

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--database', required=True)
    p.add_argument('--data-dir', type=Path, required=True)
    p.add_argument('--addons-path', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    assert re.fullmatch(r'COMMUNITY_CERRO_BOM_[A-Z0-9_]+', args.database) and not args.output.exists()
    config.parse_config(['-c', args.config, '-d', args.database, '--addons-path=' + args.addons_path,
                         '--data-dir=' + str(args.data_dir), '--db_host=/var/run/postgresql',
                         '--logfile=' + str(args.data_dir / 'graph.log'), '--no-http', '--max-cron-threads=0'])
    module.initialize_sys_path()
    providers = set(module.get_modules())
    roots = sorted(n for n in providers if n.startswith('step_cerro_studio_') or n in
                   {'step_cerro_bom_company', 'step_cerro_product_account_views'})
    assert len(roots) == 11
    wanted = set()
    missing = {}
    def visit(name, path):
        if name in path:
            raise ValueError('Cycle in proposed Cerro addon graph')
        if name not in providers:
            return {name}
        if name not in missing:
            manifest = module.get_manifest(name)
            if manifest.get('license') not in FREE or not manifest.get('installable', True):
                return {name}
            wanted.add(name)
            unmet = set()
            for dep in manifest.get('depends', []):
                unmet.update(visit(dep, (*path, name)))
            missing[name] = unmet
        return missing[name]
    blockers = {name: sorted(visit(name, ())) for name in roots}
    with sql_db.db_connect(args.database).cursor() as cr:
        cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        graph = Graph()
        graph.add_modules(cr, sorted(wanted))
        actual = set(graph.keys())
        assert all((not unmet) == (root in actual) for root, unmet in blockers.items())
        cr.execute("SELECT name,license,latest_version FROM ir_module_module WHERE state='installed'")
        installed = {n: (license, v) for n, license, v in cr.fetchall()}
        for name in actual & installed.keys():
            # A same-name Community manifest does not replace the data contract of an Enterprise provider.
            if installed[name][0] == 'OEEL-1':
                raise ValueError('Native Enterprise package requires independent migration: ' + name)
        result = {'database':args.database, 'roots':blockers, 'resolved':sorted(actual),
                  'admitted_roots':sorted(n for n in roots if n in actual),
                  'native_installed':len(installed), 'native_enterprise':sum(v[0]=='OEEL-1' for v in installed.values())}
    with args.output.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
