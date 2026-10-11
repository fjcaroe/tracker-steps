"""Inspect the installed native Gantt data method and Date handling."""
import importlib
import inspect
from pathlib import Path

try:
    root=Path(importlib.import_module('odoo.addons.web_gantt').__file__).parent
    model=env['step.export.sales.program.line']
    for name in ('get_gantt_data','get_gantt_groups','web_read'):
        if hasattr(model,name):
            method=getattr(model,name)
            print('METHOD',name,inspect.signature(method))
            if name.startswith('get_gantt'):print(inspect.getsource(method)[:14000])
    for file in root.rglob('gantt_model.js'):
        lines=file.read_text().splitlines()
        for index,line in enumerate(lines):
            if 'deserializeDate' in line or 'get_gantt_data' in line or 'date_start' in line and 'type' in line:
                print('CLIENT', '\n'.join(lines[max(0,index-3):index+10]))
finally:
    env.cr.rollback()
