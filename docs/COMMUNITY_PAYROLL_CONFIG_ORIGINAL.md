# Configuración original de nómina: captura y puertas de adopción

Estado vigente y siguiente bloque: [COMMUNITY_CONFIGURACION_NOMINA.md](COMMUNITY_CONFIGURACION_NOMINA.md).
El cierre de catorce campos y el reporte almacenado no adoptan los maestros ni
certifican la conversión integral; el contenido inferior conserva su alcance histórico.

Auditoría del 29-10-2026, desde la canónica `6e3c8298`. Complementa
[COMMUNITY_PAYROLL_ADOPCION.md](COMMUNITY_PAYROLL_ADOPCION.md),
[COMMUNITY_HR_PAYROLL.md](COMMUNITY_HR_PAYROLL.md),
[COMMUNITY_PAYROLL_API.md](COMMUNITY_PAYROLL_API.md) y
[COMMUNITY_SYS_REFERENCE.md](COMMUNITY_SYS_REFERENCE.md).

La configuración original todavía no está adoptada por OCA. Esta auditoría
identifica el almacén, los permisos y las diferencias que deben cerrarse antes
de importar. No instala campos, modifica bases, evalúa reglas ni recalcula
liquidaciones. La referencia nativa conserva Enterprise y no acredita una
conversión del motor.

## Captura privada C y procedencia

La cápsula completa está fuera del checkout:
`/opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json`.
Permisos comprobados: `0600`. SHA256:
`14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140`.

La cápsula declara `read_only=true`, `orm_loaded=false`,
`rules_evaluated=false`, `historical_payroll_read=false`,
`engine_converted=false`, `financial_certified=false` e
`import_authorized_by_capsule=false`. Su sellado no acredita que el destino
esté preparado para importar; faltan las garantías técnicas descritas abajo.
No se publican su contenido, fórmulas, traducciones privadas, identificadores
personales ni el mapa de empresas y diarios.

| Maestro o relación capturados | Filas |
| --- | ---: |
| `hr.payroll.structure` | 4 |
| `hr.payroll.structure.type` | 5 |
| `hr.payslip.input.type` | 6 |
| `hr.salary.rule` | 71 |
| `hr.salary.rule.category` | 34 |
| Total de maestros | **120** |
| M2M estructura/tipo de entrada | **0** |
| XML IDs de los cinco modelos | **91** |

Las cero asociaciones M2M de entradas son un resultado del origen. No se
rellenan con datos demo. Las reglas nativas pertenecen a su estructura por
`struct_id`; cualquier asociación M2M requerida por OCA debe expresar esos
mismos vínculos originales sin sustituir reglas ni inventar un padre.

La cápsula conserva las referencias externas y su clasificación.
`unresolved_company_properties=[]` significa que las propiedades del origen
fueron interpretadas; las referencias externas mantienen
`target_adopted=false`. Todavía falta comprobar su identidad y funcionamiento
en el destino.

## Diez campos ausentes del destino Community auditado

La comparación usa las copias privadas B de Cerro nativo y Community/OCA de
la aceptación anterior. `hr_configuration_scope_audit.py --native-gaps`,
commit `c8d81b1a`, fuerza `transaction_read_only=on`; no carga ORM ni lee
columnas con código salarial. Evidencia privada:
`/opt/steps-validation/community-hr-configuration-gaps-20261029-c8d81b1/`
(`native.json` y `community.json`). Los diez campos carecen de declaración y
columna en esa referencia Community.

| Modelo / campo original | Uso real | Puerta que falta cerrar |
| --- | --- | --- |
| Regla: `condition_other_input_id` | 71 NULL; Many2one a `hr.payslip.input.type` | Conservar relación/NULL. Rechazar una modalidad no soportada antes de calcular; no simular su semántica. |
| Regla: `amount_other_input_id` | 71 NULL; mismo destino | Mismo contrato; no convertir la relación en texto ni calcular una entrada ficticia. |
| Regla: `partner_id` | 71 NULL; Many2one a `res.partner` | Conservar identidad y política de relación para la ruta contable real. |
| Regla: `not_computed_in_net` | 47 False, 24 NULL, cero True | Preservar también el NULL físico. No admitir True sin una implementación compatible y certificada. |
| Regla: `split_move_lines` | 5 True y 66 NULL | Los cinco True pertenecen a la estructura inactiva. Conservarlos; falta certificar la separación contable antes de habilitar esa ruta. |
| Estructura: `active` | 3 True y 1 False | Conservar archivo y visibilidad. La estructura inactiva no debe activarse ni entrar en cálculo por omisión. |
| Estructura: `hide_basic_on_pdf` | 4 NULL | Conservar representación; verificar su comportamiento con el reporte Community real. |
| Estructura: `payslip_name` | 4 NULL | Conservar NULL y contrato de nombre; no rellenar nombres para completar la importación. |
| Estructura: `report_id` | Las 4 apuntan a la acción 462 | Cerrar una alternativa Community real, su identidad y permisos antes de adoptar la referencia. |
| Estructura: `journal_id` | 3 propiedades JSONB pobladas y 1 NULL | Conservar todas las empresas/diarios y usar el contexto de la compañía de la liquidación al contabilizar. |

Las cinco relaciones Many2one de esta tabla son originales directas,
almacenadas, opcionales y editables, con política declarada `ondelete=set null`.
Eso no demuestra una FK física para propiedades JSON. Los booleanos y el
nombre también son almacenados, opcionales y editables. Esto documenta el
contrato observado; no basta con añadir campos homónimos para cerrar la API.

Las 71 reglas usan únicamente estas combinaciones de selectores:
12 con condición `none` / importe `code` y 59 con condición `python` /
importe `code`. Ninguna usa los dos selectores de entrada de la tabla. Eso
reduce el caso inicial que debe certificarse; no demuestra compatibilidad de
modalidades que no están en los datos originales. No se modifica ninguna
fórmula para hacer verde el diagnóstico.

## País, empresa, permisos y traducciones

Auditoría SQL y del registro, sin registros ORM ni llamadas al proveedor:
`/opt/steps-validation/community-hr-configuration-scope-20261029-8f133df/`
(`native.json` y `community.json`). Herramienta versionada:
[hr_configuration_scope_audit.py](../tools/community/hr_configuration_scope_audit.py).

| Contrato | Origen nativo | Referencia Community/OCA auditada |
| --- | --- | --- |
| Estructuras | Sin `company_id`; un país Chile y tres países NULL | `company_id` requerido y físicamente NOT NULL; sin `country_id` propio en la estructura OCA |
| Reglas | Sin empresa ni país; `struct_id` obligatorio | Empresa opcional con default de la compañía actual; selección por relaciones OCA |
| Categorías | Sin empresa ni país | Empresa opcional con default de la compañía actual |
| Tipos de estructura | País opcional; dos globales, dos Bélgica y uno Chile | API oficial con país; los defaults del destino no prueban el país del origen |
| Tipos de entrada | País opcional; los seis globales | País oficial existente; debe conservarse NULL |

En origen, estructuras, tipos y entradas tienen reglas globales por país:
globales o de los países de las compañías permitidas del usuario. Las reglas
salariales aplican ese mismo alcance a través de `struct_id.country_id`.
Las categorías originales no tienen regla de país. No debe inventarse país
para las categorías ni propietario para maestros globales.

La adaptación propuesta API `18.0.1.8.0` permite empresa NULL en estructuras,
mantiene el default de empresa para nuevas altas ordinarias y conserva su FK
`RESTRICT`; añade el país opcional con `SET NULL` y el alcance por país de
estructuras, reglas y entradas. Las comprobaciones de jerarquía, compañía,
reglas ocultas, orden `(sequence,id)` y fallback de contratos siguen cerradas.
Al adoptar originales se debe escribir explícitamente `company_id=NULL` donde
el origen no tiene propietario, para evitar apropiación por el default.
La aceptación del paquete que contiene esta adaptación corresponde al
coordinador; esta hoja no declara aceptado ese candidato.

Las ACL tampoco son idénticas: el usuario de nómina nativo puede gestionar
reglas salariales, mientras el oficial de nómina OCA sólo las lee y el gestor
las administra. El destino es más restrictivo en ese punto. No se amplían
permisos automáticamente para resolverlo: falta comparar los roles originales,
sus XML IDs, herencias y casos de acceso normal. Los números internos de grupos
no son intercambiables entre bases. La adaptación de país no añade concesiones
ACL; sus reglas deben intersectar las reglas de empresa ya existentes.

| Campo | Diferencia observada | Tratamiento requerido |
| --- | --- | --- |
| `hr.payslip.input.type.name` | Char no traducible nativo; traducible en Community | Transformación explícita y sin pérdida entre escalar y JSON de traducciones, sin inventar traducciones ni sustituir el texto original. |
| `hr.salary.rule.note` | HTML traducible nativo; no traducible en Community | Los 71 valores originales son NULL. Preservarlos; la metadata aún difiere y debe tener un contrato explícito. |
| `hr.payroll.structure.type.name` | Requerido nativo; opcional en Community | Mantener todos los nombres originales; no depender de la menor exigencia del destino. |
| Códigos de regla y categoría | Requeridos nativos; opcionales en Community | Preservar valores, unicidad efectiva y su selección; no aceptar blancos introducidos por el destino. |

Los nombres de estructuras son no traducibles en ambas referencias, y los
nombres de reglas y categorías son traducibles en ambas. No hay una conversión
de nombre de estructura a JSON que justifique omitir el guard Chile. Cualquier
adopción de metadata debe comparar todas las propiedades, XML IDs y ACL,
incluidas las lenguas que no se modifican; no admitir diferencias genéricas de
presentación como excepción de preservación.

## Propiedades JSON de diarios y cuentas

`hr.payroll.structure.journal_id` es `company_dependent=True` y su columna
nativa es JSONB. Las tres propiedades pobladas conservan cuatro claves de
compañía cada una: 12 valores originales que remiten a cuatro diarios reales.
La estructura restante conserva NULL. No se publica el mapa privado.

La forma conceptual es `{"<company_id>": <journal_id>}`. Hay que conservar el
objeto completo y comprobar cada extremo de las relaciones. No se convierte en
un diario escalar, el primer valor ni el valor visible en la compañía actual.
La ruta de asientos debe resolver la propiedad con la compañía real de la
liquidación, verificar diario/empresa y permisos, y conservar el resultado al
cambiar las compañías permitidas del usuario.

`hr.salary.rule.account_debit` y `account_credit` ya son propiedades
`company_dependent=True` en ambas referencias. La cápsula clasifica cero
referencias pobladas de esas dos cuentas y de `analytic_account_id`; no aporta
una configuración contable certificada. No se aplanan sus columnas, asignan
cuentas por conveniencia, ni se reactiva la cuenta 210233 descontinuada.
`target_adopted=false` sigue siendo un bloqueo aunque la captura haya resuelto
todas las claves del origen.

## Reporte original 462

Las cuatro estructuras apuntan a `ir.actions.report` 462:
XML ID `hr_payroll.action_report_payslip`, modelo `hr.payslip`, tipo
`qweb-pdf` y nombre `hr_payroll.report_payslip_lang`. El vínculo depende del
reporte Enterprise. Esta auditoría no exporta ni copia su plantilla.

Antes de importar el vínculo hay que disponer de un reporte Community real,
con plantilla, traducciones, acceso por rol y flujo de impresión completos.
El plan debe cerrar la identidad del registro original, su XML ID y las
referencias de las cuatro estructuras, y detectar colisiones del ID 462 antes
de escribir. Una colisión con otro registro no autoriza sobrescribirlo. No se
admite una acción vacía, una plantilla ficticia ni dejar la FK apuntando a un
reporte distinto sin una decisión explícita y comprobable de adopción.

La aceptación incluye imprimir una liquidación nueva autorizada con usuario
normal, PDF legible, conceptos/importes coincidentes y aislamiento entre
compañías. Leer o imprimir un histórico no puede recalcular sus importes.

## Siguiente bloque: adopción real en Community nueva sin demo

1. Cerrar las declaraciones, relaciones, almacenamiento, metadata, reportes y
   permisos de los diez campos antes de importar. Implementar sólo semántica
   respaldada por el origen y API real; rechazar modalidades no certificadas.
   Mantener las guardas financieras e históricas activas.
2. Preparar una base privada nueva con Community oficial y OCA fijados, sin
   Enterprise, datos demo ni documentos de negocio. Inventariar los maestros
   inevitables del núcleo y detectar colisiones de IDs/XML IDs. Conservar los
   120 IDs originales, los 91 XML IDs, NULL/False, traducciones y vínculos; no
   borrar maestros ajenos ni usar los demos BASIC/GROSS/NET.
3. Comprobar la clausura de países, compañías, diarios, cuentas, tipos de
   entrada/trabajo, tipos de estructura y reporte. Adoptar los objetos JSON
   completos y los enlaces originales de reglas. La cápsula no incluye una
   autorización para inventar ninguno de esos maestros.
4. Ejecutar la importación atómica con plan previo, respaldo decodificado y
   comparación reproducible antes/después bajo
   `/run/lock/steps-environments.lock`. Una sola cola para crear, restaurar y
   actualizar; overlays privados y reservas mínimas de 5 GiB PostgreSQL/WAL y
   2 GiB artefactos. Un fallo revierte el destino privado; no se reparan
   correlativos originales con `setval` ni restauraciones posteriores.
5. Contrastar hashes privados de fórmulas y datos, IDs, relaciones, ACL,
   metadata, XML IDs y estados activos. Probar selección y menús con los roles
   originales, países y compañías permitidas. Una importación SQL exitosa no
   certifica el motor ni el acceso normal.
6. Certificar con la referencia real SyS: contratos, calendario y work entries
   generadas, entradas, 71 reglas, redondeos/YTD, asientos, Previred y libro.
   Usar casos nuevos y referencia aprobada; conservar exactamente las
   liquidaciones pagadas/validadas y sus componentes originales. La preparación
   SyS de dos FK `RESTRICT` y cuatro columnas ya probada es SQL, no conversión
   de identidad/metadata ORM. No eliminar su distinción.
7. Resolver con esa referencia los diagnósticos de BASIC/GROSS/NET y el
   desacople GROSS/BASIC original de Cerro. No cambiar la fórmula original,
   enlazar demos o desactivar guardas para hacer pasar el caso. La ruta
   contable debe producir asientos reales balanceados, con diario por empresa,
   reglas y permisos correctos; Previred/libro deben ser reales y no vacíos.
8. Probar el mismo paquete exacto en Community oficial y copia fresca aislada
   de Cerro; registrar por separado referencia nativa y conversión. Guardar
   evidencia privada, commits, push e integrar sólo lo validado. Ejecutar
   `python tools/git/verify_handoff.py --require-pushed` al cerrar.

Las pruebas deben usar el CLI real de Odoo y sus transacciones de test; no
ejecutar manualmente un `TransactionCase` desde shell. Los fixtures crean sus
maestros y secuencias propios o nombres explícitos; no consumen ni restauran
correlativos originales. No recalcular pagadas/validadas, escribir producción,
retirar allí Enterprise, cambiar vencimientos, usar `step_expire_database`,
refrescar QA-Cerro, emitir al SII real, enviar mensajes ni copiar fuentes OEEL.
Se mantienen Calendar, el Boolean bancario legado y 210233 descontinuada.

La aceptación B usada como referencia en COMMUNITY_PAYROLL_ADOPCION.md tiene
254 casos Community / 215 nativos, cero fallos, preservando la referencia; no
se atribuye esa aceptación a la cápsula C ni a los diez campos pendientes. Después de
adoptar la configuración siguen la identidad histórica completa del motor,
consumidores HR y las puertas de DTE/CAF/SII, Tesorería, Calidad,
Studio/Documentos/Firma y demás productos. Sólo una copia integral restaurable
con cero Enterprise y aceptación cumple
[COMMUNITY_AUTONOMIA.md](COMMUNITY_AUTONOMIA.md). La fecha del 31 de octubre
sigue en riesgo alto; esta captura parcial no resuelve el vencimiento ni
autoriza el corte de producción.

## Prompt de continuación

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS.md,
> ~/.odoo/environments.json, operación, workflow, COMMUNITY_CONTINUACION.md,
> la última aceptación, COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md,
> COMMUNITY_PAYROLL_ADOPCION.md, COMMUNITY_SYS_REFERENCE.md y
> COMMUNITY_AUTONOMIA.md. Cierra los diez campos originales, el reporte 462,
> propiedades JSON de diarios/cuentas y el contrato de roles antes de adoptar
> la cápsula privada C en Community nueva sin demo. Conserva los 120 maestros,
> cuatro estructuras, 71 reglas, seis entradas y 91 XML IDs originales, todas
> sus relaciones y fórmulas sin cambios. Comprueba colisiones y referencias
> externas; no inventes propietarios, maestros ni BASIC/GROSS/NET demo.
> Certifica casos reales nuevos con la referencia SyS, contabilización,
> Previred/libro y preservación de pagadas. Mantén las guardas financieras,
> DTE/CAF/SII y conversión integral visibles. Respeta las restricciones y el
> bloqueo compartido; prueba paquete exacto CE/copia fresca Cerro, guarda
> commits, push, integra lo validado y verifica handoff. No declares resuelto
> el 31 por adoptar una configuración parcial.
