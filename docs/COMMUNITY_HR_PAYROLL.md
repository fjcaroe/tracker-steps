# HR operacional y candidato de Nómina Community

## Alcance y contratos

`step_hr` 18.0.1.10.0 conserva la aplicación Actividades original, sus menús,
acciones de cliente, assets, Tracker, sincronización, configuración e histórico.
Declara Movilización como consumidor real del dashboard. Los modelos, tablas,
relaciones a empleados/flota y permisos existentes no se copian ni se sustituyen.
La aplicación puede instalarse con fuentes oficiales Community sin Nómina ni mapa
Enterprise. Los núcleos agrícolas y laborales mantienen sus raíces alternativas
inactivas cuando existe la raíz original de HR, también en instalaciones nuevas.
Los verificadores distinguen existencia de la raíz de la edición del servidor.

`step_hr_payroll_bridge` depende de los modelos reales de `hr_payroll`, del puente
`step_labor_payroll_wizards`, de HR y de `web_map`. Conserva `hr.payslip.net_liquido`,
las relaciones de Cuadrillas al lote/estructura, el método real de Tarjas hacia
entradas de trabajo y las cuatro vistas originales. Adopta sus XML IDs antes de
la limpieza de módulos y protege los alias de modelos/campos, incluido el campo
delegado de `res.users`. No crea otro modelo de liquidación ni permisos nuevos.
Debe instalarse explícitamente en la copia de Cerro al actualizar HR; quitar
simplemente las dependencias de HR sin instalar este puente pierde el contrato.
La premigración rechaza actualizar HR con Nómina instalada si el puente no está instalado o programado en el mismo paquete. No se despliega en servicios activos en este bloque.

El override legado `res.partner.duplicate_bank_partner_ids` sigue siendo Boolean
en Cerro a través del puente. Una instalación Community nueva conserva el
Many2many nativo de Contabilidad. Esto **no** convierte el Boolean histórico en
relación ni permite retirar el puente sin una migración bancaria específica.
Los límites visuales de Calendar y la cuenta `210233` descontinuada siguen vigentes.

## Auditoría del proveedor y del motor

`tools/community/audit_payroll_community.py` consulta solo Cerro con sesiones
PostgreSQL forzadas a lectura. Audita los manifiestos efectivos, huellas de fuentes,
modelos, campos, firmas de métodos, llamadas a `super`, referencias de reglas y
configuración de estructuras/entradas/Previred/libros. No publica cuerpos de reglas,
datos de trabajadores, configuración del servidor ni secretos. El resultado se
guarda fuera del checkout. La licencia declarada no acredita compatibilidad de API.

La fuente efectiva de Simple Digital declara AGPL-3 y versión 18.0.1.0.0, pero
sus dependencias `hr_payroll`, `hr_payroll_account` y `hr_payroll_expense` son
OEEL-1. El primero depende a su vez de entradas de trabajo Enterprise. No basta
cambiar esos nombres ni retirar Enterprise de producción para convertir el motor.

Se fija el candidato real [OCA/payroll](https://github.com/OCA/payroll/tree/4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e),
con módulos `payroll` 18.0.1.4.0 y `payroll_account` 18.0.1.0.6, LGPL-3.
Se ensaya en una base Community nueva y aislada: motor nativo, reglas/contratos,
entrada, cálculo y contabilización propios; nunca un stub de `hr.payslip`.
Este ensayo **no** adapta ni instala Simple Digital sobre OCA.

| Contrato requerido por el stack actual | Brecha a cerrar con OCA |
| --- | --- |
| Módulos y XML IDs `hr_payroll*` | OCA usa `payroll*`; hay que adaptar dependencias y adoptar IDs de modelos, grupos, reglas, acciones y vistas sin fachadas vacías. |
| `hr.payroll.structure.type`, `hr.contract.structure_type_id` | Los modelos base sí existen en Community oficial. OCA usa además `hr.contract.struct_id`; faltan el enlace `hr.payroll.structure.type_id` y los complementos del proveedor, conservando IDs y semántica. |
| `hr.salary.rule.struct_id` | OCA usa reglas asociadas a estructuras por M2M; falta conservar la relación original y demostrar equivalencia. |
| `hr.payslip.input.type` e `input_type_id` | OCA usa entradas con código y `hr.rule.input`; faltan tipos, restricciones por estructura e identidad de entradas originales. |
| `hr.payslip.worked_days.work_entry_type_id` y `_get_worked_day_lines_values(domain)` | Simple Digital genera asistencia/ausencias por tipos de entradas; OCA no ofrece esa misma API. No reemplazarla por días constantes. |
| `_get_line_values`, alcance líquido y contexto de reglas | Las reglas reales usan métodos, `env`, instituciones y relaciones del registro de liquidación. Hay que adaptar el contexto del motor con cálculo real y conservar las líneas originales. |
| Nómina contable/gastos | Conciliar asientos, diarios, cuentas, gastos y redondeos del motor real, sin recalcular liquidaciones pagadas. |
| Previred y libro | Mantener contratos del proveedor, controlador de salida, 105 campos/variantes, mapeos DT, estados, instituciones, permisos y cifras; certificar resultados con casos chilenos. |

Inventario de la auditoría: 4 estructuras, 5 tipos de estructura, 71 reglas,
6 tipos de entrada, 8 tipos de movimiento, 2 perfiles Previred y 2 perfiles de
libro con 42 líneas de mapeo. No hay contratos, liquidaciones, entradas de trabajo,
movimientos ni exportaciones históricas en esta base. Las pruebas con fixtures
no acreditan una conversión de liquidaciones pagadas reales ni certificación
normativa chilena. La auditoría incluye los puentes efectivos de Previred,
libro, ciclo de contratos, correcciones y transición del motor.

## Importación masiva sobre Nómina real

El wizard original ya no busca la primera liquidación o contrato del empleado.
Exige empresa activa, lote, estructura, un empleado por usuario y una liquidación
única coincidente. Toma bloqueo de filas, vuelve a leer estados y valida todo el
conjunto antes de crear entradas. Solo acepta lote abierto (`draft`/`verify`) y liquidación en borrador y no
pagada, conserva el contrato de la propia liquidación y rechaza un tipo de entrada
ya existente. Una repetición no duplica importes ni reemplaza registros originales.
No usa `sudo`, no concede el ACL ausente del wizard y no llama a `compute_sheet`.
La API nativa cambia el lote a `verify` al agregar una liquidación todavía en borrador; se conserva esa semántica y se rechazan lotes `close`/`paid`. El flujo APR legado sigue separado y no constituye un motor salarial.

## Pruebas y evidencia

El perfil `hr` de `tools/community/validate_agriculture_core.py` incorpora toda
la regresión agrícola anterior, HR operacional y el puente opcional en Cerro.
Compara el paquete completo de addons por archivo, los datos, identidades,
permisos, traducciones, históricos y contadores. El upgrade se mide antes de
las fixtures; el consumo posterior de secuencias estándar queda identificado,
monótono y sin resetear contadores. Incluye tablas originales de Tracker, histórico
y Nómina, no solo las tablas agrícolas previas.

`tools/community/validate_payroll_engine.py` fija el commit OCA y exige fuentes
limpias oficiales, DB privada nueva y bloqueo compartido. Ejecuta las pruebas
del proveedor OCA y un flujo nativo de cálculo/asiento balanceado como usuario
sin superpoderes. El resultado enumera la API faltante y mantiene
`simpledigital_compatible=false` hasta cerrar la adaptación real.

La evidencia de aceptación se registra al completar ambos ensayos; las etapas
fallidas o exploratorias nunca equivalen a validación del paquete final.

## Camino crítico al 31 de octubre

A 27-10-2026, quedan cuatro días hasta la fecha indicada. El cierre operacional
de HR libera dependencias, pero no resuelve el vencimiento. No hay evidencia
suficiente para comprometer un corte integral seguro el 31; riesgo alto.

1. Adaptar el motor salarial real para Simple Digital y preservar contratos,
   tipos, estructuras, reglas, entradas, estados y contabilización. Probar los
   casos chilenos y la equivalencia de Previred/libro, además de históricos reales.
2. Cerrar DTE/CAF/folios/certificados/firmas/respuestas SII y Exportación; ensayar
   sin emisión real ni reutilización de folios de producción.
3. Cerrar Calidad, Studio, Documentos/Firma, lotes/conciliación de Tesorería y
   consumidores todavía Enterprise, incluidas apps sin fuentes consolidadas.
4. Convertir una copia integral fresca con **cero Enterprise**, comparar datos,
   saldos, permisos e históricos; ensayar restauración y aceptación por perfil.
5. Revisar en Desarrollo y ejecutar el circuito de publicación autorizado con
   paquete exacto, respaldo, ventana y recuperación. QA-Cerro conserva sus datos.

Producción mantiene 140 Enterprise. No se modifica la fecha de vencimiento ni
se interpreta una extracción parcial o una prueba aislada de OCA como solución.
