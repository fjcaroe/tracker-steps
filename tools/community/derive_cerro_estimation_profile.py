"""Compose the two native Cerro estimate contracts for the first construction of a restored registry."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

COSTS = 'step_management_costs'
PLOTS = 'step_management_estimation_entry'
EXPECTED = {
    (COSTS, 'models/estimation.py'): 'eeeb1a66238969dc924cca782111e7b19d380e69b135820f336dbe240c769eda',
    (COSTS, '__manifest__.py'): '8b3a763f910881b4dafe2b55fda73c5ebb54addf8b8053849cacf027d1d941a7',
    (PLOTS, 'models/plot.py'): '67262417c43b04b404a365616ce193791b4f6250ba5fd6aa5e7a73a214a95192',
    (PLOTS, '__manifest__.py'): '154afcd6883f73188dda9885cca646f85d504fae5ad7b4bb13d57454c72dea51',
}


def field_span(text, class_name, field):
    node, = [n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == class_name]
    item, = [n for n in node.body if isinstance(n, ast.Assign)
             and any(isinstance(value, ast.Name) and value.id == field for value in n.targets)]
    return item.lineno - 1, item.end_lineno


def derive(costs_source, plots_source, output):
    source = {COSTS: costs_source, PLOTS: plots_source}
    checked = {}
    for (module, file), expected in EXPECTED.items():
        data = (source[module] / file).read_text(encoding='utf-8')
        if hashlib.sha256(data.encode()).hexdigest() != expected:
            raise ValueError('The admitted upstream definition changed: ' + module + '/' + file)
        checked[module, file] = data
    original = checked[COSTS, 'models/estimation.py']
    plot = checked[PLOTS, 'models/plot.py']
    original_lines = original.splitlines(keepends=True)
    plot_lines = plot.splitlines(keepends=True)
    start, end = field_span(original, 'StepManagementEstimationLine', '_sql_constraints')
    source_parts = []
    for field in ('cuartel_id', '_sql_constraints'):
        a, b = field_span(plot, 'EstimationLine', field)
        source_parts.append(''.join(plot_lines[a:b]))
    original_lines[start:end] = ['\n'.join(source_parts)]
    revised = ''.join(original_lines)
    manifest = checked[COSTS, '__manifest__.py']
    old = '"depends": ["base", "mail", "web", "account", "product", "stock", "purchase"]'
    if manifest.count(old) != 1 or manifest.count('"18.0.21.1.0"') != 1:
        raise ValueError('Unexpected cost module dependencies')
    manifest = manifest.replace(old, old[:-1] + ', "step_agriculture_core"]').replace('"18.0.21.1.0"', '"18.0.21.1.1"')
    ast.literal_eval(manifest)
    ast.parse(revised)
    if output.exists():
        raise ValueError('Choose a new private profile directory')
    output.mkdir(parents=True)
    for module, root in source.items():
        shutil.copytree(root, output / module, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (output / COSTS / 'models/estimation.py').write_text(revised, encoding='utf-8', newline='\n')
    (output / COSTS / '__manifest__.py').write_text(manifest, encoding='utf-8', newline='\n')
    return {'costs_sha256': hashlib.sha256(revised.encode()).hexdigest(),
            'manifest_sha256': hashlib.sha256(manifest.encode()).hexdigest(),
            'plot_owner_sha256': EXPECTED[PLOTS, 'models/plot.py']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--costs-source', type=Path, required=True)
    parser.add_argument('--plots-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.costs_source, args.plots_source, args.output), sort_keys=True))
