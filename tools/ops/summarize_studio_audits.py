"""Reconcile metadata inventories with loaded-menu audits into a private report."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path, marker):
    text = path.read_text(encoding='utf-8')
    assert marker in text.splitlines(), 'Incomplete audit: ' + str(path)
    rows = []
    for line in text.splitlines():
        if line.startswith(('STUDIO_', 'INVENTORY_')) and ' ' in line:
            kind, data = line.split(' ', 1)
            rows.append((kind, json.loads(data)))
    return rows


def owned(row):
    return any(x.startswith('studio_customization.') for x in row['xmlids'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-directory', type=Path, required=True)
    parser.add_argument('--stamp', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root), 'Private evidence must stay outside Git'
    report = {}
    for environment in ('development', 'steps', 'sys', 'demo-sys', 'cerro'):
        inventory_path = args.input_directory / ('studio-inventory-%s-%s.jsonl' % (environment, args.stamp))
        menu_path = args.input_directory / ('studio-current-%s-%s.jsonl' % (environment, args.stamp))
        inventory = read(inventory_path, 'STUDIO_INVENTORY_OK')
        menus = read(menu_path, 'STUDIO_AUDIT_OK')
        summary = next(r for k, r in inventory if k == 'INVENTORY_SUMMARY')
        fields = [r for k, r in inventory if k == 'INVENTORY_FIELD']
        studio_pairs = {(r['model'], r['name']) for r in fields if owned(r)}
        objects = [r for k, r in inventory if k == 'INVENTORY_OBJECT']
        manual_models = [r for k, r in inventory if k == 'INVENTORY_MODEL']
        manual_names = {r['model'] for r in manual_models}
        manual_menus = [r for k, r in menus if k in ('STUDIO_MENU', 'STUDIO_OTHER_MANUAL_MENU') and r['model'] in manual_names]
        effective = [dict(r, studio_manual_dependencies=[pair for pair in r['manual_dependencies'] if tuple(pair) in studio_pairs])
                     for k, r in inventory if k == 'INVENTORY_EFFECTIVE_VIEW']
        row = {
            'counts': {k: summary[k] for k in ('manual_models', 'manual_fields', 'active_studio_views')},
            'studio_owned_manual_fields': len(studio_pairs),
            'other_manual_fields': len(fields) - len(studio_pairs),
            'manual_models_with_records': sum(bool(m['record_count']) for m in manual_models),
            'active_studio_automations': sum(r['kind'] == 'base.automation' and r.get('active') and r['studio_owner'] for r in objects),
            'studio_reports': sum(r['kind'] == 'ir.actions.report' and r['studio_owner'] for r in objects),
            'visible_internal_manual_menu_count': sum(r['visible_internal'] for r in manual_menus),
            'visible_admin_manual_menu_count': sum(r['visible_administrator'] for r in manual_menus),
            'manual_model_menu_paths': manual_menus,
            'effective_views': effective,
            'effective_view_errors': [r for k, r in inventory if k == 'INVENTORY_EFFECTIVE_ERROR'],
            'scoped_view_errors': [r for k, r in menus if k == 'STUDIO_VIEW_ERROR'],
            'manual_models': manual_models,
            'studio_manual_fields': [r for r in fields if owned(r)],
            'objects': objects,
            'native_models_with_remaining_manual_fields': [r for k, r in menus if k == 'STUDIO_MODEL' and r['state'] == 'base' and r['manual_fields']],
            'source_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (inventory_path, menu_path)},
        }
        report[environment] = row
        print(json.dumps({'environment': environment, **row['counts'],
            **{k: row[k] for k in ('studio_owned_manual_fields', 'other_manual_fields', 'active_studio_automations', 'studio_reports', 'visible_internal_manual_menu_count')},
            'compiled_studio_primary_views': len(effective),
            'view_errors': len(row['effective_view_errors']) + len(row['scoped_view_errors'])}, ensure_ascii=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('STUDIO_RECONCILIATION_SAVED ' + str(args.output))


if __name__ == '__main__':
    main()
