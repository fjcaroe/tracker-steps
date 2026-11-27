"""Compare original Cerro user navigation, Studio fields and complete web-client reads."""
import argparse
import json
from pathlib import Path


def receipt(path, marker):
    lines = [line for line in path.read_text().splitlines() if line.startswith(marker + ' ')]
    if len(lines) != 1:
        raise ValueError('Expected one ' + marker + ' receipt in ' + str(path))
    return json.loads(lines[0].split(' ', 1)[1])


def compare(native_full, native_routes, candidate):
    reference = native_routes['views']['qualified']
    current = candidate['client']['qualified']
    keys = ('uid', 'fields', 'record_id', 'read_sha256')
    if len(native_full) != 23 or set(reference) != set(native_full):
        raise ValueError('The complete native 23-view control is required')
    if any(set(keys) - values.keys() for values in reference.values()):
        raise ValueError('The native Studio fields receipt is incomplete')
    matching_values = sorted(name for name in reference.keys() & current.keys()
                             if all(reference[name][key] == current[name][key] for key in keys))
    native_paths = native_routes['routes']['direct_menu_routes']
    paths = candidate['routes']['direct_menu_routes']
    matching_paths = sorted(view for view in native_paths.keys() & paths.keys()
                            if any(source['action'] == target['action'] and source['kind'] == target['kind']
                                   and set(source['menus']) & set(target['menus'])
                                   for source in native_paths[view] for target in paths[view]))
    complete = sorted(name for name, row in native_full.items()
                      if 'value_sha256' in row and row == candidate['fullread'].get(name))
    return {'reference_views': len(native_full), 'matching_full_record': complete,
            'matching_studio_values': matching_values, 'original_routes': matching_paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-full', type=Path, required=True)
    parser.add_argument('--native-routes', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--marker', choices=('PACKING_STUDIO','BUDGET_STUDIO'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    matches = compare(receipt(args.native_full, 'CERRO_FULL_READ'), receipt(args.native_routes, 'CERRO_FULL'),
                      receipt(args.candidate, args.marker))
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(matches, output, sort_keys=True)


if __name__ == '__main__':
    main()
