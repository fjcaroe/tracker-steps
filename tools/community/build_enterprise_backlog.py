"""Publish dependency metadata only; private audit paths/parameters stay private.

The matrix is a removal gate, not a declaration that an unused addon is safe
to uninstall. Runtime data use and a complete conversion rehearsal are required.
"""
import argparse
import ast
import json
from pathlib import Path


def closure(name, nodes, seen=None):
    seen = set() if seen is None else seen
    if name in seen:
        return seen
    seen.add(name)
    for dependency in nodes.get(name, {}).get('depends', []):
        closure(dependency, nodes, seen)
    return seen


def family(name):
    if name.startswith('l10n_cl_') or name == 'certificate':
        return 'DTE / Chile'
    if 'quality' in name or name == 'worksheet':
        return 'Calidad'
    if name.startswith(('hr_', 'planning', 'base_automation_hr_contract')):
        return 'Personal / Nómina / Planificación'
    if name.startswith(('account', 'analytic', 'currency_', 'snailmail_account')):
        return 'Contabilidad / Tesorería'
    if name.startswith(('documents', 'sign', 'website_documents')):
        return 'Documentos / Firma'
    if name.startswith(('stock_', 'mrp_', 'purchase_')):
        return 'Inventario / Fabricación'
    if name.startswith(('project_', 'sale_')):
        return 'Proyectos / Ventas'
    return 'Interfaz / Integraciones'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding='utf-8'))
    installed = {m['name']: dict(m, depends=m.get('manifest_depends', m['depends'])) for m in audit['modules']}
    candidates = dict(installed)
    for manifest in args.repository.glob('*/__manifest__.py'):
        candidates[manifest.parent.name] = ast.literal_eval(manifest.read_text(encoding='utf-8-sig'))
    enterprise = sorted(m for m, n in installed.items() if n.get('license') == 'OEEL-1')
    own = sorted(m for m in installed if m.startswith('step'))
    previous = {m: closure(m, installed) for m in own}
    proposed = {m: closure(m, candidates) for m in own}
    pending = [m for m in own if proposed[m] & set(enterprise)]
    rows = ['# Matriz de retiro Enterprise — Cerro, 27-10-2026', '',
            'Generada con `tools/community/build_enterprise_backlog.py` desde auditoría de solo lectura.',
            'No contiene datos de negocio, rutas de servidor ni parámetros de licencia.', '',
            f'Producción: {len(installed)} módulos instalados, {len(enterprise)} Enterprise y {len(own)} propios.',
            f'Código candidato: {len(pending)} apps propias instaladas aún alcanzan Enterprise por sus dependencias.',
            'Producción conserva Enterprise. Ninguna fila autoriza desinstalación ni acredita reemplazo integral.',
            'Las columnas cuentan apps propias instaladas cuya clausura declarada alcanza cada módulo;',
            '«código candidato» usa los manifiestos del checkout. Cero dependientes propios no significa cero uso.', '',
            '| Módulo Enterprise | Familia | Apps en producción | Código candidato | Puerta de retiro |',
            '| --- | --- | ---: | ---: | --- |']
    for name in enterprise:
        rows.append(f'| `{name}` | {family(name)} | {sum(name in c for c in previous.values())} | '
                    f'{sum(name in c for c in proposed.values())} | Pendiente de ensayo integral |')
    rows += ['', '## Dependencias Enterprise directas de nuestras apps', '',
             'Esta lista usa producción; los puentes ya extraídos se mantienen instalados allí.', '',
             '| App | Dependencias directas en producción |', '| --- | --- |']
    for name in own:
        direct = sorted(set(installed[name]['depends']) & set(enterprise))
        if direct:
            rows.append('| `' + name + '` | ' + ', '.join('`' + n + '`' for n in direct) + ' |')
    rows += ['', '## Apps propias con caminos Enterprise pendientes', '',
             'Se cuentan las apps propias del inventario instalado, no los puentes nuevos opcionales.',
             '«Fuente en repo» solo indica disponibilidad del manifiesto; no acredita aceptación funcional.',
             'Los sustitutos agrícolas y HR probados no equivalen a conversión integral del destino.', '',
             '| App | Caminos Enterprise | Fuente en repo |', '| --- | ---: | --- |']
    for name in pending:
        rows.append('| `' + name + '` | ' + str(len(proposed[name] & set(enterprise))) + ' | ' +
                    ('Sí' if (args.repository / name / '__manifest__.py').exists() else 'Pendiente de consolidar') + ' |')
    rows += ['', '## Orden de desbloqueo y aceptación', '',
             '1. Maestros agrícolas y centros de costo: núcleo Community con modelos/IDs originales; '
             'luego consumidores de Packing, Productores, Costos y Exportación.',
             '2. Nómina y contratos: motor Community compatible, reglas chilenas, liquidaciones, '
             'Previred y libro de remuneraciones; conservar contratos y liquidaciones históricas.',
             '3. Tesorería: lotes nativos existentes, conciliación operativa y clasificación del efectivo. '
             'Las cinco consultas alternativas ya no requieren account_reports.',
             '4. DTE y exportación: CAF, folios, firmas, libros, guías, respuestas SII e históricos. '
             'No declarar equivalencia por instalar una localización genérica.',
             '5. Calidad, calendarios y demás interfaz: reemplazar operaciones reales y vistas, '
             'inventariar Studio, adjuntos, documentos, firmas y configuraciones antes de retirar.',
             '6. Arranque de una copia integral con fuentes Community exclusivamente; comparar '
             'IDs, tablas, permisos, saldos y flujos por empresa y perfil; ensayar recuperación.', '',
             'No editar controles de vencimiento ni usar stubs Enterprise. El addon legado '
             '`step_expire_database` forma parte del inventario, no de los reemplazos autorizados.',
             'El corte final requiere paquete integral probado y respaldo fresco; esta matriz '
             'no demuestra que el riesgo del 31 de octubre esté resuelto.', '']
    args.output.write_text('\n'.join(rows), encoding='utf-8')
    print(json.dumps({'enterprise_rows': len(enterprise), 'own_modules': len(own),
                      'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
