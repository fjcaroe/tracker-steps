# Frontera operacional Community: Maquinaria y Tareas

## Contrato del paquete

`step_operations_core` 18.0.1.0.0 depende del núcleo agrícola, `hr` y `project`
nativos. Adopta 30 campos existentes: 16 de `fleet.vehicle`, nueve de
`hr.employee` y cinco de `project.task`. No crea maestros, empleados, flota,
tablas de negocio, grupos ni ACL paralelos. Conserva tipos, relaciones y
columnas; las tres vistas y la acción de flota conservan sus registros.

`ownership.py` declara los 34 identificadores explícitos. Los hooks adoptan
los registros originales antes de cargar datos y mantienen los alias
`step_hr.*`, incluidas las selecciones de los campos adoptados. Un conflicto
de modelo o destino aborta la instalación; no se elige silenciosamente otro ID.
Los alias legados quedan protegidos contra la limpieza del upgrade de HR.

Las variedades de las tareas permanecen opcionales, como en el esquema
efectivo de Cerro con `step_project_agriculture_scope`. Ese consumidor sigue
aplicando sus restricciones agrícolas cuando corresponde al centro de costo.
Una tarea genérica no recibe una variedad inventada. Se conserva el método
de costo horario legado, sin cambiar fórmulas ni recalcular liquidaciones.

`step_hr` 18.0.1.7.0 consume el núcleo y deja de declarar/importar esos campos
y vistas. Conserva Nómina, Tarjas y sus dependencias Enterprise pendientes.
`step_machinery` 18.0.22.1.0 consume el núcleo en lugar de HR propio y declara
`portal` explícitamente por su mixin. `step_project_agriculture_scope`
18.0.1.1.0 consume el mismo núcleo. El puente existente
`step_management_costs_machinery` entra en el perfil de aceptación completo.

## Permisos y comprobación funcional

Se mantienen los permisos de los modelos nativos y los de Maquinaria. La
prueba del empleado usa un usuario de RRHH y comprueba costos, moneda y
relaciones; un usuario portal carece de acceso al empleado privado. La prueba
HTTP de Maquinaria utiliza un usuario desechable de prueba y nunca cambia
contraseñas ni grupos de usuarios existentes del destino.
La precisión monetaria se comprueba con el redondeo de la moneda efectiva,
incluido CLP. La prueba contable usa una empresa desechable y su propio plan
de cuentas: la copia de Cerro conserva la cuenta canónica de provisión
`210233` descontinuada. No se reactiva ni se sustituye esa cuenta para aprobar
una prueba. La contabilización real de Cerro que intente usarla continúa
bloqueada por la validación nativa; resolver su configuración requiere una
decisión contable y una prueba específica antes de aceptar ese flujo real.

`validate_agriculture_core.py --profile operations` incluye los doce módulos
agrícolas/Productores previos y estos cuatro módulos operacionales. La prueba
pura omite `step_hr` y utiliza exclusivamente el checkout oficial Community.
La copia fresca conserva Enterprise para verificar compatibilidad de upgrade;
no acredita una conversión integral. El verificador nativo abre formularios y
guarda un parte de maquinaria y una tarea con usuarios autorizados, sin modo
superusuario; revierte sus altas al terminar.

Además de los contratos contables, agrícolas y de Productores, se comparan
todas las tablas `project_*`, `fleet_*`, `monthly_*`, `real_cost_*`,
`regist_cost_*` y los tipos de servicio/costeo de maquinaria. Se exige
conservación de modelos, campos, selecciones, ACL, reglas, menús, enlaces de
acciones/vistas, membresías, históricos, adjuntos y vencimiento. Las dos
excepciones visuales de Gantt a Calendar son únicamente las documentadas en
`COMMUNITY_PRODUCTORES.md`; no se modifica el override bancario legado.

El perfil operacional excluye del contrato de adjuntos únicamente los bundles
binarios CSS/JS públicos generados de `ir.ui.view`, sin campo, `res_id=0` y URL
hexadecimal `/web/assets/…`. Se comparan estrictamente los demás adjuntos,
incluidos archivos privados, de vistas y mapas fuente. La excepción se prueba
con `test_attachment_cache_postgres.py` sobre fixtures temporales PostgreSQL.
El ensayo D conserva también los contratos sin filtrar. Su cierre con
`recheck_operations_contract.py` verifica los dos logs completos de 408 pruebas,
los hashes del paquete y los verificadores nativos, restaura el dump original
en una base SQL privada nueva y exige que coincida con la línea base original
antes de filtrar cachés. No permite aceptar pruebas fallidas ni addons cambiados.

## Alcance pendiente

No cambiar todavía los manifiestos de Tarjas, Cuadrillas, registros agrícolas
o Movilización que usen `step.tarja`, costos laborales, contratos o nómina.
`step_mobilization_agriculture` distribuye costos a través de Tarjas: necesita
una extracción de modelos y relaciones comprobada, sin sustituirlos por texto
o un cálculo aproximado. No retirar Enterprise de producción ni modificar
vencimientos. Tampoco refrescar QA-Cerro.

El siguiente inventario debe cerrar conjuntamente `step.tarja`,
`step.tarja.line`, `step.tarja.cost.line`, `step.tarja.registry` y las
cuadrillas `hr.salary.custom`. Hay relaciones a `hr.contract`, tarifas de
`product.pricelist`, banderas legales de empresa y `step.haber.costeo`.
Movilización utiliza la tarja propia del mismo fundo/fecha/empresa para
resolver empleado, centro y labor. Mantener esa semántica y sus históricos
antes de separar cualquier adaptador hacia Nómina.

La aceptación y las rutas de evidencia del ensayo final se registran en
`COMMUNITY_CONTINUACION.md`. Las cifras de la matriz corresponden a caminos
de manifiestos candidatos; no certifican todos los flujos de la base.
