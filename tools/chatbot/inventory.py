"""Read-only environment inventory. Never print credentials or env contents."""
import configparser
import glob
import json
import os
import subprocess

for path in sorted(glob.glob('/etc/*odoo18*.conf')):
    config = configparser.ConfigParser(interpolation=None)
    config.read(path)
    options = config['options']
    print(json.dumps({'config': path, **{key: options.get(key) for key in
        ('db_name', 'dbfilter', 'addons_path', 'http_port', 'data_dir')}}, ensure_ascii=False))
    for directory in options.get('addons_path', '').split(','):
        directory = directory.strip()
        print(json.dumps({'addons_directory': directory, 'exists': os.path.isdir(directory), 'realpath': os.path.realpath(directory)}))
print(subprocess.check_output(['systemctl', 'list-units', '--all', '--plain', '--no-legend', 'odoo18*'], text=True))
