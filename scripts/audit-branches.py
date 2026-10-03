"""Write a branch/worktree inventory without exposing file contents or changing branches."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo


def git(*args, cwd=None):
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    branches = git('for-each-ref', '--format=%(refname:short)', 'refs/heads').splitlines()
    prs = json.loads(subprocess.check_output(['gh', 'pr', 'list', '--state', 'open', '--limit', '100', '--json', 'number,headRefName,baseRefName,url'], text=True))
    pr_by_branch = {p['headRefName']: p for p in prs}
    lines = ['# Revisión de ramas y worktrees', '',
             f'Fecha: {datetime.now(ZoneInfo("America/Santiago")).isoformat(timespec="minutes")}.', '',
             '## Ticket 46 — consolidado', '',
             'Rama canónica: `codex/steps-movil`. Las ocho ramas históricas están integradas por historia,',
             'incluyendo las dos variantes divergentes de I1. No queda un commit del ticket 46 fuera de la base canónica.',
             'Se conservaron las referencias históricas para trazabilidad; no son destinos de despliegue.', '',
             'La integración conserva I2, I4–I8, I12 parcial, I13 e I14/I15 parciales, mapa, rutas y confirmación de GPS.',
             'Las variantes antiguas de I1 se adaptaron: no se retoma automáticamente una jornada por centro de costo',
             'ni se borra una jornada porque no aparezca en una lista limitada. Consulta local por ID y revalidación al volver a primer plano.', '',
             'Pendientes funcionales: I3/I16 requieren herramientas y cuentas para Android/iOS; I9–I11 diseño de pasajeros;',
             'incidentes en Odoo, enlace de gastos con rendiciones y pruebas en teléfonos reales siguen pendientes según el plan.', '',
             '## Inventario completo', '',
             'Los conteos contra `develop` indican trabajo aún no incluido allí; no implican que falte respaldo o que deba desplegarse todo junto.',
             'Las instrucciones vigentes mantienen producción del Web Tracker en `codex/web-tracker-redesign`.', '',
             '| Rama | HEAD | Local/origin (delante/detrás) | Commits fuera de develop | PR abierto |',
             '|---|---|---|---:|---|']
    for branch in branches:
        remote = f'origin/{branch}'
        try:
            delta = '/'.join(git('rev-list', '--left-right', '--count', f'{branch}...{remote}').split())
        except RuntimeError:
            delta = 'sin rama remota'
        ahead = git('rev-list', '--count', f'origin/develop..{branch}')
        p = pr_by_branch.get(branch)
        pr = f'[#{p["number"]}]({p["url"]}) → `{p["baseRefName"]}`' if p else '—'
        lines.append(f'| `{branch}` | `{git("rev-parse", "--short", branch)}` | {delta} | {ahead} | {pr} |')
    lines += ['', '## Comprobación de integración del ticket 46', '', '| Rama histórica | Commits fuera de la canónica |', '|---|---:|']
    for b in branches:
        if b.startswith('ticket/46-'):
            missing = git('rev-list', '--count', f'codex/steps-movil..{b}')
            lines.append(f'| `{b}` | {missing} |')
            if missing != '0':
                raise RuntimeError(f'Unintegrated ticket 46 branch: {b}')
    lines += ['', '## Cambios locales fuera de Git', '',
              'Se revisaron todos los worktrees registrados. No se añadieron masivamente archivos temporales, documentos ni respaldos al repositorio público.', '',
              '| Worktree / rama | Archivos versionados modificados | Archivos no versionados |', '|---|---:|---:|']
    for item in git('worktree', 'list', '--porcelain').split('\n\n'):
        parts = item.splitlines()
        if not parts:
            continue
        path = parts[0].removeprefix('worktree ')
        branch = next((p.removeprefix('branch refs/heads/') for p in parts if p.startswith('branch ')), 'detached')
        changed = git('status', '--porcelain', '--untracked-files=no', cwd=path).splitlines()
        untracked = git('ls-files', '--others', '--exclude-standard', cwd=path).splitlines()
        lines.append(f'| `{branch}` ({Path(path).parent.name}/{Path(path).name}) | {len(changed)} | {len(untracked)} |')
        if changed:
            lines += [f'\nCambios versionados en `{branch}`: ' + ', '.join(f'`{line[3:]}`' for line in changed) + '.', '']
        if untracked:
            roots = Counter(p.split('/')[0] for p in untracked)
            lines += [f'\nNo versionados en `{branch}`: ' + ', '.join(f'`{root}` ({n})' for root, n in roots.most_common()) + '.', '']
    lines += ['', '## Siguientes consolidaciones por producto', '',
              '- Productores / inventario / packing: T35 como base de T30/T38/T40 y T41 sobre T40; revisar los PR #4, #8, #10, #11 y #12 como conjunto.',
              '- Nómina: T44 y T47 son cambios independientes pendientes de integrar con sus pruebas de remuneraciones.',
              '- Fletes: variantes T27 de Studio, mejoras y precisión analítica requieren revisión conjunta.',
              '- Tesorería: T28 aprobación está encima de T28 BancoEstado; consolidar esa cadena.',
              '- Tracker y costos: las ramas de costos, unificación y Web Tracker tienen destinos distintos; revisar PR #14 sin alterar la rama productiva del Web Tracker.',
              '- Otras entregas: T22–T25, T34, T39, T42, T43, homepage y soporte conservan sus ramas/PR según la tabla.', '',
              'No se fusionaron módulos ajenos al ticket 46 ni se descartaron los archivos locales pendientes. Esta revisión registra exactamente lo pendiente; su integración funcional requiere pruebas y destinos por módulo.', '']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines), encoding='utf-8')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
