"""Add the static portal ONLY to the three requested SSL virtual hosts."""
import re
from pathlib import Path

targets = {'desarrollo.stepsapp.cl', 'demo.stepsapp.cl', 'cerroelplomo.stepsapp.cl'}
seen = set()
for link in Path('/etc/nginx/sites-enabled').iterdir():
    path = link.resolve()
    content = path.read_text()
    matches = list(re.finditer(r'\bserver\s*\{', content))
    inserts = []
    for match in matches:
        depth = 1
        end = match.end()
        while end < len(content) and depth:
            if content[end] == '{': depth += 1
            if content[end] == '}': depth -= 1
            end += 1
        block = content[match.start():end]
        names = re.search(r'\bserver_name\s+([^;]+);', block)
        if not names or not re.search(r'listen\s+[^;]*443', block): continue
        hosts = set(names[1].split()) & targets
        if not hosts: continue
        if '/etc/nginx/snippets/steps-tracker-portal.conf' not in block:
            if 'location ^~ /web_tracker/' in block:
                raise RuntimeError('Existing tracker location needs review: '+str(path))
            inserts.append(match.end())
        seen |= hosts
    for at in reversed(inserts):
        content = content[:at]+'\n    include /etc/nginx/snippets/steps-tracker-portal.conf;\n'+content[at:]
    if inserts:
        path.write_text(content)
        print('Updated virtual host file:', path)
if seen != targets:
    raise RuntimeError('Missing HTTPS virtual hosts: '+str(targets-seen))
