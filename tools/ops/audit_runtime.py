"""Read safe configuration, addon versions and Studio field metadata on odoo-new."""
import ast
import configparser
import hashlib
import json
from pathlib import Path
import subprocess


def query(database, sql):
    return subprocess.check_output(['sudo', '-n', '-u', 'postgres', 'psql', '-d', database, '-Atc', sql], text=True).strip()


def main():
    configs = []
    for path in sorted(Path('/etc').glob('*odoo*.conf')):
        try:
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(path)
            opts = cfg['options']
        except (configparser.Error, KeyError):
            continue
        row = {'config': str(path), **{k: opts.get(k) for k in ('db_name', 'dbfilter', 'http_port', 'http_interface', 'proxy_mode', 'addons_path', 'data_dir')}}
        database = row['db_name']
        if database and ',' not in database:
            sql = "SELECT COALESCE(json_agg(t),'[]'::json) FROM (SELECT name,state,latest_version FROM ir_module_module WHERE name LIKE 'step%' AND state='installed' ORDER BY name) t"
            try:
                row['modules'] = json.loads(query(database, sql))
                row['base_url'] = query(database, "SELECT value FROM ir_config_parameter WHERE key='web.base.url'")
                row['base_url_freeze'] = query(database, "SELECT value FROM ir_config_parameter WHERE key='web.base.url.freeze'")
                paths = [Path(p.strip()) for p in opts['addons_path'].split(',')]
                for module in row['modules']:
                    for directory in paths:
                        manifest = directory / module['name'] / '__manifest__.py'
                        if manifest.exists():
                            metadata = ast.literal_eval(manifest.read_text())
                            module['manifest_version'] = metadata.get('version')
                            module['source'] = str(manifest.parent)
                            digest = hashlib.sha256()
                            for file in sorted(manifest.parent.rglob('*')):
                                if file.is_file() and file.suffix in {'.py', '.xml', '.csv', '.js', '.css', '.scss'} and '__pycache__' not in file.parts:
                                    digest.update(str(file.relative_to(manifest.parent)).encode())
                                    digest.update(file.read_bytes().replace(b'\r\n', b'\n'))
                            module['sha256'] = digest.hexdigest()
                            break
            except subprocess.CalledProcessError:
                row['database_unavailable'] = True
        configs.append(row)
    print(json.dumps(configs, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
