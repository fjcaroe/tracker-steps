"""Install reviewed Odoo agent instructions and normalize existing API URLs.

Run locally. Credentials are retained and never printed; private backups are
outside Git. No scheduler cadence, notification setting or API key is changed.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit
import xmlrpc.client

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
BEGIN = '<!-- BEGIN STEPS ODOO MANAGED CONTROLS -->'
END = '<!-- END STEPS ODOO MANAGED CONTROLS -->'


def main():
    registry = json.loads((ROOT / 'tools/ops/environments.json').read_text())
    backup = HOME / '.codex/local-artifacts/ambientes-canonicos' / ('agent-controls-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True)
    installed = {}

    def replace(path, data):
        original = path.read_bytes() if path.exists() else None
        if original == data:
            return
        if original is not None:
            (backup / (path.parent.name + '-' + path.name)).write_bytes(original)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Reject a concurrent writer rather than silently replacing its work.
        assert (path.read_bytes() if path.exists() else None) == original, 'Concurrent change: ' + str(path)
        path.write_bytes(data)
        installed[str(path)] = hashlib.sha256(data).hexdigest()

    replace(HOME / '.odoo/environments.json', (ROOT / 'tools/ops/environments.json').read_bytes())
    replace(HOME / '.claude/scheduled-tasks/correos-fcaro-gestion-costos/SKILL.md',
            (ROOT / 'tools/ops/claude_ticket_workflow.md').read_bytes())
    global_file = HOME / '.claude/CLAUDE.md'
    old = global_file.read_text(encoding='utf-8-sig') if global_file.exists() else ''
    block = '''
Estas reglas aplican solo al repositorio Odoo Steps (fjcaroe/tracker-steps).
Leer ~/.odoo/environments.json y docs/OPERACION_ODOO_CANONICA.md antes de cambiar
o publicar Odoo. Si ese documento falta en un checkout antiguo, leerlo con
git show origin/codex/ambientes-canonicos-reparacion:docs/OPERACION_ODOO_CANONICA.md.
No elegir la base por el checkout abierto. Usar worktree propio y respetar
las decisiones vigentes: Desarrollo es el único QA y lugar de revisión.
Demo-SYS solo Nómina Simple Digital y soporte de Luis. Producción únicamente
SyS, Steps / karo_consultorias y Cerro El Plomo. Demo, Admin y Everfruit quedan
fuera del circuito de publicación; preservar datos, no usarlos como QA.
las ramas canónicas de los productos. Los puertos tienen dominios HTTPS:
8075 es Desarrollo, 8070 SyS, 8069 Steps; consultar el registro para los demás.
Hay acceso SSH documentado; no declarar inaccesible un ambiente solo por un
fallo de API o de acceso a IP/puerto. No imprimir ni cambiar credenciales.
No sustituir relaciones a maestros por campos de texto ni crear tablas paralelas.
No parchear Studio manualmente para simular código ni mezclar sus menús con
una aplicación nueva. Versionar la migración y preservar los registros.
Una migración/vista/permiso requiere pruebas funcionales en una copia del
destino. Publicar el mismo paquete probado, con respaldo, bloqueo compartido
/run/lock/steps-environments.lock, ausencia de downgrade y de cambios concurrentes.
Usar overlays privados; no sobrescribir raíces de addons compartidas.
No cerrar tickets por un análisis, commit o HTTP 200: comprobar versión,
formulario, menú y flujo real en el ambiente solicitado. Incorporar respuestas
humanas recientes antes de repetir preguntas. Guardar commits, push y ejecutar
python tools/git/verify_handoff.py --require-pushed. No tocar cambios ajenos.
'''.strip()
    managed = BEGIN + '\n' + block + '\n' + END
    if BEGIN in old:
        assert END in old
        prefix, remainder = old.split(BEGIN, 1)
        _, suffix = remainder.split(END, 1)
        updated = prefix + managed + suffix
    else:
        updated = old.rstrip() + ('\n\n' if old.strip() else '') + managed + '\n'
    replace(global_file, updated.encode('utf-8'))
    migrated = []
    for profile in sorted((HOME / '.odoo').glob('*_api.json')):
        config = json.loads(profile.read_text(encoding='utf-8-sig'))
        parsed = urlsplit(config.get('url', ''))
        target = None
        if parsed.hostname == registry['public_ip']:
            target = next((t for t in registry['environments'].values() if t['port'] == parsed.port), None)
        else:
            target = next((t for t in registry['environments'].values() if urlsplit(t['url']).hostname == parsed.hostname), None)
        if not target or config.get('db') != target['database']:
            continue
        url = 'https://soporte.stepsapp.cl' if profile.name == 'helpdesk_api.json' else target['url']
        if config.get('url', '').rstrip('/') == url:
            continue
        assert parsed.path in ('', '/'), 'Unexpected API path: ' + profile.name
        common = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common')
        try:
            uid = common.authenticate(config['db'], config['username'], config['api_key'], {})
        except Exception:
            raise RuntimeError('Canonical authentication failed for ' + profile.name) from None
        assert uid, 'Canonical authentication rejected for ' + profile.name
        config['url'] = url
        replace(profile, (json.dumps(config, ensure_ascii=False, indent=2) + '\n').encode())
        migrated.append(profile.name)
    (backup / 'installed.json').write_text(json.dumps({'files': installed, 'migrated_profiles': migrated}, indent=2))
    print('AGENT_CONTROLS_INSTALLED ' + json.dumps({'backup': str(backup), 'changed_files': len(installed), 'migrated_profiles': migrated}))


if __name__ == '__main__':
    main()
