"""Inspect native Gantt popover source for field context without business data."""
import odoo.addons.web_gantt as addon
from pathlib import Path
root=Path(addon.__file__).parent
for file in root.rglob('*.js'):
    text=file.read_text()
    if 'popoverTemplate' in text or 'gantt-popover' in text:
        for needle in ('popoverTemplate','gantt-popover'):
            start=0
            while (index:=text.find(needle,start))>=0:
                print(str(file.relative_to(root)),text[max(0,index-160):index+400])
                start=index+len(needle)
