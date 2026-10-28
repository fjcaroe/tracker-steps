# Plan de independencia de Enterprise para Cerro El Plomo

Autorizado por el usuario el 27-10-2026: preparar el plan y comenzar su ejecución,
conservando datos y funcionalidad de los módulos propios. La ejecución empieza
en entornos privados de ingeniería, dentro del circuito de Desarrollo. No se
autoriza una desinstalación masiva en producción ni un refresco de QA-Cerro.

## Criterio de término

La copia convertida debe arrancar con fuentes Community, cero módulos OEEL-1
instalados y sin dependencias Enterprise de los módulos Steps que se publiquen.
Debe conservar maestros, claves, relaciones, históricos, documentos, adjuntos,
permisos y saldos, y aprobar los flujos reales. Ocultar el aviso, cambiar la
fecha de vencimiento o quitar nombres del manifiesto no cumplen este objetivo.

La producción actual sigue siendo Enterprise durante la preparación. El aviso
del 31 de octubre no queda resuelto por las primeras extracciones de código.
No hay una fecha de corte comprometida antes de completar las pruebas.

## Secuencia de trabajo

| Etapa | Trabajo concreto | Condición para avanzar |
| --- | --- | --- |
| 0 Inventario y control | Congelar inventario de módulos, licencias, dependencias, datos y campos manuales. Registrar sustituto y prueba de cada componente usado. Añadir comprobación automática de dependencias. | Evidencia privada reproducible; ninguna pérdida aceptada implícitamente. |
| 1 Base contable | Separar campos, cálculos y formularios multimoneda del motor Enterprise de informes. Preservar IDs, XMLIDs y valores históricos al adoptar campos/vistas. | Arranque puro Community; prueba de actualización en copia fresca de Cerro; integridad de valores e IDs; pagos y conciliación vigentes. |
| 2 Informes y Tesorería | Sustituir accesos y adaptadores a `account_reports` y lotes Enterprise. Evaluar informes OCA y construir adaptadores propios donde se requieran valores operacionales históricos. Desacoplar `step_account_treasury`, sus puentes y T123. | Balance, mayor, antigüedad, flujo de caja, exportaciones y pagos concuerdan con los documentos y permisos. |
| 3 Maestros y personal | Separar maestros agrícolas/operación de `step_hr` respecto de Gantt y Nómina Enterprise. Mantener los modelos, registros y relaciones existentes. Encapsular nómina y entradas de trabajo en puentes. Evaluar motor Community compatible con Simple Digital. | Packing y Productores instalan sin Nómina Enterprise; contratos e históricos conservados; ninguna liquidación pagada recalculada. |
| 4 Exportación y Chile | Separar operación comercial de `l10n_cl_edi_exports`. Implementar/adoptar localización Community y puente DTE compatible con SII. Inventariar certificados, CAF y documentos sin exponer secretos. | Pruebas tributarias y de exportación en ambiente de ensayo; ninguna emisión real durante la migración. |
| 5 Calidad e interfaz | Reemplazar `quality_control`, Gantt y demás extensiones usadas con código propio o componentes Community. Inventariar campos/vistas/reglas heredados y transferir su propiedad antes de retirar Studio. | Flujos completos, no solo portadas; historial y formularios accesibles; campos manuales conservados. |
| 6 Conversión integral | Ensayar el retiro ordenado de Enterprise en una copia actual de Cerro, con fuentes Community exclusivamente. Ejecutar todas las regresiones y conciliaciones. | Cero Enterprise, datos íntegros, restauración ensayada y aceptación funcional. |
| 7 Publicación | Preparar paquete exacto, ventana, respaldo íntegro y bloqueo compartido. Verificar versión, formulario, menú y flujos después de publicar. Migrar QA conservando sus ejercicios mediante un proceso independiente. | Producción verificada; plan de recuperación; evidencia de aislamiento de QA. |

Las etapas 2 y 3 pueden diseñarse de forma independiente, pero cada integración
debe resolver las dependencias de su paquete antes de instalarlo. No se crean
tablas alternativas para los mismos maestros ni sustitutos vacíos de módulos
Enterprise para engañar al cargador.

## Primer paquete en ejecución

Se extrae `step_accounting_multicurrency_core`, LGPL-3, dependiente solo de
`account`. Mantiene los mismos campos en `res.company`, `account.move`,
`account.move.line`, pagos y registro de pagos, y las mismas columnas SQL.
`step_accounting_multicurrency` pasa a ser el puente opcional a los informes
Enterprise; conserva su nombre para no romper a los módulos que todavía lo usan.

La adopción de metadatos crea XMLIDs del núcleo sobre los registros anteriores
y conserva los XMLIDs antiguos como alias. No duplica vistas o campos. La prueba
de retiro de un namespace de alias comprueba la protección nativa de Odoo cuando
otro módulo mantiene la propiedad. Esto no equivale todavía a desinstalar toda
la edición Enterprise ni garantiza el retiro del puente con sus dependientes.

Este primer paquete no desacopla aún Tesorería ni los otros 79 módulos afectados.
Libera una base necesaria y establece el procedimiento para las siguientes
extracciones. Los cambios se mantienen sin publicar en ambientes activos hasta
completar su validación y el circuito de entrega correspondiente.

## Candidatos y decisiones pendientes

- [OCA Financial Reports 18.0](https://github.com/OCA/account-financial-reporting/blob/18.0/account_financial_report/__manifest__.py)
  depende de `account`, `date_range` y `report_xlsx`, con licencia AGPL-3.
  Es candidato para mayor, balance de comprobación y antigüedad. No se ha
  instalado ni se declara reemplazo completo de los informes existentes.
- [OCA Payroll 18.0](https://github.com/OCA/payroll/blob/18.0/payroll/__manifest__.py)
  se evaluó fijado a `4c71cd4`: 38 pruebas y cálculo/asiento nativo en Community
  oficial. No acredita todavía compatibilidad con Simple Digital, reglas de
  Chile ni datos históricos; ver `docs/COMMUNITY_HR_PAYROLL.md`.
- Facturación electrónica chilena requiere una selección y validación específicas;
  no se presume que un módulo de localización genérico sustituye DTE/CAF/SII.
- Las funciones que no se usen se podrán retirar solo después de inventariar
  registros y dependencias; no se interpretan datos vacíos como prueba suficiente.

## Evidencia y continuidad

Inventario inicial: `docs/CERRO_EDICION_Y_DEPENDENCIAS_20261026.md` y artefactos
privados de esa auditoría. Son metadatos de referencia, no un respaldo actual
para una publicación futura. Cada ensayo utiliza una copia fresca del destino.

Validación del primer paquete: `tools/community/validate_finance_foundation.py`.
El script solo acepta bases privadas, toma bloqueo compartido y no tiene modo
de despliegue. Las evidencias, dumps y capturas quedan fuera del repositorio.

Estado y comandos de continuación se registran en
`docs/COMMUNITY_CONTINUACION.md` al terminar esta sesión.

## Avance comprobado al 27-10-2026

Primera extracción completada y validada, sin despliegue en servicios activos:
11 pruebas en una instalación oficial Community con cero Enterprise y 35 pruebas
sobre una copia fresca de Cerro, incluidas las 24 de pagos por factura. Los
valores de 839 tablas y los 21 IDs de campos se conservaron. La huella textual
adicional registra un cambio de escala `15.00`/`15` en envases, sin cambio de
valor. Tres pruebas SQL comprueban que el comparador no redondea importes ni
convierte textos, y dos pruebas validan la conservación de FKs del maestro.

El ensayo Cerro conserva sus 140 Enterprise: es una prueba de extracción, no
la conversión final. Producción sigue con la versión previa y el vencimiento
permanece pendiente. Evidencias y punto exacto de continuación están en
`docs/COMMUNITY_CONTINUACION.md`.

## Segunda extracción: frontera de Tesorería

`step_account_treasury` 18.0.1.3.0 usa el núcleo multimoneda Community.
Los cinco accesos a `account_reports` pasan a `step_account_treasury_reports`
18.0.1.0.0, puente opcional que también conserva el adaptador multimoneda de
informes. Los modelos, cálculos, exportaciones de planificación y permisos de
Tesorería siguen en el módulo original, con sus nombres y tablas.

Al actualizar una base existente se debe instalar el puente en la misma
operación (solo en el ensayo privado, con las demás opciones del validador):

```text
-i step_accounting_multicurrency_core,step_account_treasury_reports
-u step_accounting_multicurrency,step_account_treasury
```

La premigración rechaza
una actualización que dejaría sin propietario los accesos anteriores. Adopta
los cinco menús mediante alias, sin escribir sus acciones, grupos, padres,
secuencias ni estado activo. El hook del puente solo crea los accesos faltantes:
el XML con `noupdate` también escribe al instalar un módulo nuevo, por lo que
no se usa para adoptar estos menús.

Esto es una extracción de dependencias, no la sustitución de los cinco informes.
Una instalación Community dispone de planificación, detalle, resumen y
exportaciones de Tesorería; no anuncia conciliación bancaria, mayor de socios,
estado de flujo de efectivo ni antigüedad Enterprise. En la copia Enterprise
los cinco accesos siguen disponibles con sus IDs anteriores. No desinstalar el
puente ni `account_reports`: todavía faltan sus sustitutos y el tratamiento de
los lotes históricos. La etapa 2 sigue abierta hasta conciliar esos reemplazos.

`tools/community/validate_treasury_extraction.py` ensaya esta frontera en
Community y en una copia fresca de Cerro. Solo admite bases privadas, usa el
bloqueo compartido y no tiene modo de publicación. Además de las huellas de
negocio comprueba campos, menús, ACL, reglas, grupos y membresías.

## Tercer paquete: alternativas Community para los cinco accesos

`step_treasury_community_reports` 18.0.1.0.0 implementa mayor de socios,
antigüedad por cobrar/pagar, efectivo realizado y control de conciliación.
`step_account_treasury` 18.0.1.3.1 admite este reemplazo en su premigración.
Los cinco menús conservan identidad y restricciones; apuntan a acciones de
ventana propias. Las acciones compartidas de Enterprise permanecen intactas.
La instalación Community sí dispone ahora de las cinco alternativas.

El alcance y las reglas monetarias se detallan en
`INFORMES_COMMUNITY_TESORERIA.md`: consulta del libro nativo sin `sudo`, corte
histórico de conciliaciones, salidas HTML/CSV/PDF y separación de monedas.
El efectivo es realizado, todavía sin clasificación normativa por actividades;
la conciliación muestra controles y permite abrir documentos nativos, sin
publicar ni conciliar automáticamente. No se presume equivalencia de esa
presentación con toda la configuración Enterprise anterior.

El usuario autorizó el 27-10-2026 publicar este paquete en QA-Cerro para probar,
sin refrescar sus ejercicios ni tocar producción. El publicador específico
solo admite Desarrollo y QA-Cerro y exige ensayo Community, copia fresca de
Cerro y copia fresca del destino, con el mismo SHA256 por archivo. Las versiones,
fuentes, configuración y datos deben seguir correspondiendo a la prueba.
El retiro integral de Enterprise y el reemplazo de lotes siguen pendientes.

## Cuarto paquete: maestros agrícolas y consumidores Community

`step_agriculture_core` extrae 18 modelos y 181 campos declarados de los
maestros, productos y cuentas analíticas. Adopta 250 identificadores explícitos
y los metadatos heredados/generados, sin copiar tablas ni cambiar relaciones.
`step_hr` conserva el personal y las funciones que todavía requieren Enterprise;
no se debe desinstalar. Los detalles de adopción, permisos y ejecutor de
actualización están en `COMMUNITY_MAESTROS_AGRICOLAS.md`.

Catálogos compartidos, Packing, Tarjas de Fruta y el puente agrícola de Gestión
y Costos consumen el núcleo sin Nómina ni Gantt. Esto acredita esa frontera,
no la independencia del resto de las extensiones de Packing o Exportación.
El alcance compartido y la nulabilidad se conservan durante toda la carga,
además de conservarse en el registro final. No se asignan empresas por defecto
a los registros compartidos existentes.

La matriz completa de los 140 Enterprise está en
`COMMUNITY_INVENTARIO_ENTERPRISE_20261027.md`. Frente a la auditoría de
producción, el código candidato deja seis apps propias sin caminos declarados
hacia Enterprise; 73 de las 91 aún tienen alguno. Es un análisis de dependencias,
no una prueba de conversión de toda la base ni una resolución del vencimiento.
Nómina/contratos, DTE, Calidad, lotes y los demás consumidores siguen pendientes.

La autorización de revisión en QA-Cerro no autoriza refrescar su base ni retirar
Enterprise de producción. El paquete agrícola requiere todavía sus ensayos
frescos en Desarrollo y QA antes de publicar allí. Los informes de Tesorería
del paquete anterior continúan siendo el último despliegue verificado en QA.

## Quinto paquete: Productores y dos calendarios Community

El núcleo 18.0.1.1.0 adopta la ficha agrícola del contacto; Productores
18.0.1.9.0 usa ese núcleo y `hr` Community para el autorizador. Los informes
de contratos y estimaciones 18.0.1.1.0 sustituyen Gantt por calendarios nativos,
conservando acciones, vistas, enlaces, filtros, modelos y proyecciones SQL.
Modalidad de compra adapta sus vistas heredadas y el puente de costos mantiene
su relación con la cuenta analítica nativa.

El fin visual inclusivo se calcula aparte; no se alteran vencimientos ni
semanas almacenadas, cantidades, precios o importes. La ficha Community usa la
dirección nativa, conservando el mapa como puente opcional. El override bancario
booleano legado permanece en `step_hr` para no convertir silenciosamente su
tipo ni perder su columna. Ver `COMMUNITY_PRODUCTORES.md`.

El perfil `--profile producers` del validador comprende doce módulos del
paquete y añade comprobación de las dos proyecciones SQL y de los dos cambios
de modo permitidos en enlaces existentes. No permite retirar Enterprise ni
publicar servicios. Las versiones y ensayos aceptados quedan en continuidad.
El código candidato reduce a 68 las apps propias con caminos declarados hacia
Enterprise, frente a 79 en producción y 73 después del cuarto bloque.
Esta cifra no acredita una conversión integral de la base ni la independencia
de todas las extensiones de Exportación/Packing que aún dependen de Enterprise.

## Sexto paquete: frontera operacional de Maquinaria y Tareas

`step_operations_core` 18.0.1.0.0 extrae 30 campos de flota, empleados y tareas,
conservando 34 identificadores explícitos, las relaciones y las vistas originales.
`step_hr` 18.0.1.8.0 queda como consumidor del núcleo. Maquinaria 18.0.22.1.0
y clasificación agrícola de tareas 18.0.1.1.0 consumen el núcleo Community.
El puente existente de costos de maquinaria se incluye en el mismo ensayo.
El contrato técnico está en `COMMUNITY_OPERACIONES.md`.

El perfil `operations` contiene dieciséis módulos de paquete y compara también
las tablas operacionales de flota, proyectos y costos. Las comprobaciones de
permisos incluyen empleados privados, aislamiento por empresa y usuarios
autorizados sin modo superusuario. No se relajan las restricciones de las tareas
agrícolas ni se exigen variedades inventadas a las tareas genéricas.

La matriz candidata baja de 68 a 65 apps propias con caminos declarados hacia
Enterprise: se liberan Maquinaria, su puente de costos y el alcance de tareas.
Producción continúa con sus 140 Enterprise. Tarjas/Cuadrillas, Movilización y
otros consumidores de nómina necesitan su propia extracción de modelos,
relaciones, vistas y permisos antes de modificar dependencias. Las evidencias
de aceptación y los pendientes de publicación están en continuidad.

## Séptimo paquete: Tarjas, Cuadrillas y Movilización

`step_labor_operations_core` 18.0.1.0.0 separa nueve modelos operacionales de
`step_hr`, con 228 campos declarados y 296 identificadores explícitos, incluidos
nueve permisos y cuatro secuencias. Adopta también los registros originales de
propiedad de siete tablas M2M. Mantiene las tablas, IDs, relaciones, parámetros
y cálculos, sin crear maestros alternativos ni recalcular liquidaciones pagadas.
El contrato técnico está en `COMMUNITY_TARJAS_CUADRILLAS.md`.

`step_hr` 18.0.1.8.0 conserva el puente real a lotes y estructuras de Nómina y
el envío a remuneraciones; el núcleo Community no simula esos modelos.
Movilización agrícola 18.0.1.1.0 usa el núcleo laboral y lee la distribución
actual de las tarjas. Movilización 18.0.1.0.3 declara el tipo de documento
latinoamericano nativo y alinea su pestaña de tarifas con los grupos de su modelo.

El perfil `labor` ensaya diecinueve módulos de paquete y amplía el contrato de
preservación a tarifas, calendarios/recursos, relaciones M2M y restricciones
SQL/FK laborales. Las reglas de tarifa permiten completar sus relaciones
obligatorias desde ambos formularios. Las pruebas no asignan grupos a usuarios
existentes para forzar acceso ni fabrican jornadas para calcular costos.

El candidato deja 64 apps propias con caminos Enterprise: el adaptador agrícola
de Movilización abandona ese camino. Esto no convierte por sí solo los otros
consumidores de Cosecha, Nómina, DTE o Calidad. Tampoco sustituye el ensayo de
conversión integral, recuperación, publicación y aceptación. Las evidencias del
paquete aceptado quedan en continuidad; producción conserva 140 Enterprise.

## Octavo paquete: Cosecha, planificación y registros

`step_cosecha` 18.0.1.8.0 consume el núcleo laboral sin Nómina/Gantt.
`step_cosecha_planning` 18.0.1.1.0 consume los formatos compartidos;
`step_agriculture_records` 18.0.1.3.0 declara Movilización y el costo horario
nativo Community. Cosecha y sus diez modelos conservan nombres/tablas,
maestros y permisos. `product.packaging` sigue siendo el único maestro de
embalajes; no se infiere clasificación para los históricos.

`step_agriculture_format_core`, `step_labor_reports` y
`step_labor_payroll_wizards` adoptan 27 identificadores explícitos, cinco
modelos transitorios y 22 campos declarados. Los dos informes laborales son
operacionales Community. El puente de wizards conserva Nómina real y sus
relaciones en Cerro, y no se instala en Community. HR lo consume sin duplicar
las definiciones en Cosecha. Se adoptan los tres propietarios M2M pendientes.
La bandera original de recepción `stock.picking.cosecha` pasa a Cosecha con
un identificador adicional preservado: el total del bloque es 28 IDs y 23
campos declarados. Se comprueba recepción nativa y rechazo de duplicados.
No se certifica todavía el importador de entradas salariales, el algoritmo
APR legado ni el motor Simple Digital sobre un sustituto Community.

El contrato, los límites y la comprobación de correlativos se detallan en
`COMMUNITY_COSECHA.md`; la aceptación y evidencia se registran en continuidad.
La matriz candidata pasa de 64 a 59 apps propias con caminos Enterprise.
Esas cinco clausuras incluyen `step_harvest_launcher`, que solo aparece en el
inventario del servidor y no tiene fuentes versionadas en este checkout:
la cifra es de dependencias declaradas, no una certificación adicional de ese
launcher. Las cuatro aplicaciones agrícolas del paquete sí se ensayan.
Producción conserva Enterprise; siguen abiertos Nómina, DTE/CAF/SII, Calidad,
Studio/Documentos/Firma, lotes/conciliación, despliegues de los núcleos y la
conversión integral con recuperación y aceptación. No se puede comprometer
el corte del 31 de octubre a partir de esta extracción.


## Frontera operacional HR y candidato salarial — 27-10-2026

Aceptado el paquete HR `6e418ef`: 468 pruebas en Community oficial y 516 en copia
fresca de Cerro, 28 addons/837 archivos idénticos. Se conservan 918 tablas/
proyecciones, 58.956 XML IDs originales, permisos/históricos/saldos y 140
contadores durante upgrade; las fixtures consumen después 30 contadores de la
copia sin reset. HR operacional queda libre de Nómina/mapa EE, con puente real
para las relaciones, vistas, Tarjas y Boolean bancario originales.

OCA Payroll real pasa 38 pruebas y un flujo de cálculo/asiento balanceado en
Community oficial. Persisten al menos siete brechas verificadas con Simple
Digital, además de la aceptación chilena/Previred/libro e históricos pagados.
No se implementa un stub de `hr.payslip` ni se retira Enterprise en producción.

La matriz actual cubre 93 apps propias: 53 aún alcanzan Enterprise; producción
mantiene 140 EE. Sigue pendiente el camino crítico DTE/CAF/SII y la conversión
integral con cero EE, recuperación y aceptación por perfil. Riesgo alto para el
31 de octubre: este bloque no resuelve el vencimiento. Estado, evidencia y
prompt siguiente en `COMMUNITY_HR_PAYROLL.md` y `COMMUNITY_CONTINUACION.md`.


## Contratos API Simple Digital–OCA — 27-10-2026

Nuevo bloque de código `7c95671`: adaptador sobre OCA real, sin `hr.payslip`
simulado ni fachada `hr_payroll`. Paquete G: tres addons/15 archivos idénticos,
53 pruebas Community oficial (64 instalados/0 EE) y seis contratos compartidos
en copia fresca nativa de Cerro (376/140 EE). Se preservan 918 tablas/proyecciones,
140 contadores exactos incluso tras fixtures, 58.956 XML IDs, permisos, relaciones,
históricos y saldos. No se repite ni se suma la regresión HR anterior 468/516.

Se implementan tipos de entrada/FK, enlace de tipos de estructura, relación
primaria de reglas con M2M OCA, totales por código y acceso real a entradas por
diccionario. Se bloquea recálculo pagado/validado, repetición ambigua de entradas
tipadas y cambios de relación inconsistentes. `payslip` ya era un registro real
OCA; no se sustituyó. La comparación genérica incluye moneda CLP y asiento real.
Las siete brechas del inventario de API anterior son el diagnóstico inicial;
no interpretar su implementación parcial como certificación de Simple Digital.

Quedan días/ausencias/work entries, agregación, cantidades/redondeos/YTD,
instalación real del proveedor sobre OCA, adopción de modelos/campos/XML IDs/grupos,
71 reglas chilenas, Previred/libro e históricos pagados representativos. OCA
hereda líneas desde reglas: requiere mapear ese esquema en la conversión.
Siguen DTE/CAF/SII y la conversión integral con cero EE, recuperación y aceptación.
No cambian las 53 clausuras Enterprise sobre 93 apps del inventario anterior;
producción conserva 140 EE. El riesgo del 31 sigue alto y el vencimiento no
está resuelto. No se modifican producción, QA-Cerro, vencimientos ni pagadas.

Estado detallado, límites, hashes, evidencia privada reproducible y **prompt de
continuidad vigente** en [COMMUNITY_PAYROLL_API.md](COMMUNITY_PAYROLL_API.md).


## Días reales, entradas repetidas y redondeo OCA — 28-10-2026

Código `bebf5ab`, paquete F: tres addons/17 archivos idénticos, 68 pruebas
Community oficial (64/0 EE) y 15 contratos compartidos contra Nómina real en
copia fresca de Cerro (376/140 EE). Se conservan 918 tablas/proyecciones,
140 contadores exactos incluso después de fixtures, 58.956 XML IDs, relaciones,
permisos, históricos y saldos. Menú, formulario, configuración y onchange de
liquidación se comprueban con permisos normales y fixtures revertidas.

Se implementan horas/días sobre work entries y calendarios reales, tipos FK,
OUT sin maestros paralelos y actualización de días conservando IDs. El cálculo
con ese modo rechaza entradas faltantes, conflictos y relaciones heredadas sin
adoptar. Las repeticiones tipadas homogéneas ahora se evalúan y agregan sin perder
filas, incluidos conceptos no lineales, categorías y el helper de totales OCA;
la mezcla ambigua con entradas sin tipo sigue rechazada. Se contrasta el
redondeo CLP por concepto con dos escenarios del puente chileno, sin cambiarlo
en producción ni recalcular pagadas. YTD sigue explícitamente pendiente.

La copia es referencia con su motor original; no instala OCA ni representa una
conversión integral. El nuevo mapa de lectura registra diferencias de campos,
FK/M2M, HTML/selecciones/estados que deben cerrarse antes de cambiar dependencias.
Simple Digital completo, las 71 reglas, Previred/libro, históricos pagados,
DTE/CAF/SII y el ensayo integral cero EE siguen pendientes. No se actualizan
servicios activos ni QA-Cerro, no se cambian vencimientos. Siguen 53 clausuras EE
sobre 93 apps inventariadas y 140 EE en producción. El 31 continúa con riesgo alto.

Alcance vigente, hashes, evidencia, mapa y **siguiente prompt** en
[COMMUNITY_PAYROLL_WORK_ENTRIES.md](COMMUNITY_PAYROLL_WORK_ENTRIES.md).


## Instalación Simple Digital–OCA — 28-10-2026

Paquete K, código c930d5a: 80 pruebas Community oficial (68 módulos/0 EE) y
27 en copia fresca nativa de Cerro (377/140 EE), con 82 archivos idénticos.
Se conservan 918 tablas/proyecciones, 140 contadores, 58.956 XML IDs y metadatos,
permisos, relaciones, históricos y saldos originales. El proveedor real instala
sin campos faltantes ni diferencias en los atributos comparados de sus campos;
se prueban aliases de IDs originales, acceso propio/ajeno, formulario/acción e
informe. La referencia mantiene su motor: la conversión integral, almacenamiento
histórico, 71 reglas, YTD, Previred/libro y DTE/CAF/SII siguen pendientes.
El vencimiento del 31 no está resuelto. Producción y QA-Cerro no se modifican.

Estado, alcance, evidencia privada y **prompt vigente** en
[COMMUNITY_SIMPLEDIGITAL_OCA.md](COMMUNITY_SIMPLEDIGITAL_OCA.md).
La continuidad horaria autorizada y sus puertas de cierre están en
[COMMUNITY_AUTONOMIA.md](COMMUNITY_AUTONOMIA.md); la matriz completa actualizada es
[COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md](COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md).
