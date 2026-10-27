# Tarjas, Cuadrillas y Movilización Community

Actualización posterior: la frontera restante de HR se separa en
`step_hr_payroll_bridge`; Actividades/Tracker permanecen en `step_hr` Community.
Este documento conserva la evidencia de su bloque original; el contrato actual
y la continuación de Nómina están en [COMMUNITY_HR_PAYROLL.md](COMMUNITY_HR_PAYROLL.md).

## Frontera operacional

`step_labor_operations_core` 18.0.1.0.0 depende de `step_operations_core` y
de contratos, entradas de trabajo, ventas, compras y documentos latinoamericanos
nativos Community. Adopta nueve modelos existentes: `hr.salary.custom`,
`hr.salary.custom.line`, `hr.salary.contract.line`, `step.tarja`,
`step.tarja.line`, `step.tarja.cost`, `step.tarja.cost.line`,
`step.tarja.registry` y `step.haber.costeo`. Mantiene nombres y tablas SQL.

También traslada los campos propios de contratos, tarifas y sus líneas,
parámetros operacionales de empresa y las tres banderas contables. El contrato
declara 228 campos y 296 XML IDs explícitos: modelos, campos, vistas, acciones,
nueve ACL y cuatro secuencias. Los campos heredados/generados y selecciones
del dominio se adoptan también mediante alias. No crea empleados, contratos,
maestros, tablas de negocio o grupos paralelos.

Los hooks transfieren la propiedad antes de cargar el paquete, conservan
`step_hr.*` y abortan ante conflictos. Las secuencias se crean únicamente
cuando faltan; no se vuelven a escribir prefijos, contadores, compañías,
incrementos o rangos personalizados. Los registros originales de
`ir.model.relation` de las siete tablas M2M de Tarjas y tarifas se transfieren
al núcleo, conservando ID, nombre y modelo. No se copian sus relaciones.

Los nueve permisos originales se trasladan con los mismos grupos y flags.
Los formularios conservan los mismos registros y los informes sus acciones,
filtros y modelos. El menú nuevo Community se desactiva cuando existe la raíz
legada de Actividades: no introduce un atajo sobre los grupos de sus ancestros.
No se relajan ni se endurecen silenciosamente las ACL originales de Tarjas.

Las relaciones obligatorias `labor_id` y `uom_id` de las reglas de tarifa se
pueden completar tanto en el formulario embebido como en el independiente.
No se rellenan con maestros ficticios ni se modifican reglas existentes.
Movilización 18.0.1.0.3 limita su pestaña de tarifas por recorrido al grupo
que ya tiene acceso al modelo: un usuario agrícola sin ese perfil puede abrir
sus tarifas sin intentar leer líneas de transporte restringidas.
Declara además la dependencia nativa `l10n_latam_invoice_document`: su campo
de tipo de documento de empresa no debe reflejarse como `_unknown` por el
orden de carga. La prueba comprueba el comodel y una relación guardada real.

## Contratos, costos y puente de Nómina

Se conservan las fórmulas, tasas y campos almacenados de costo. En Cerro, el
adaptador de horas semanales sigue leyendo `hours_per_week` cuando ese campo
está disponible; es propiedad de `hr_payroll`, no de contratos Community.
En Community calcula las horas desde las asistencias globales nativas,
excluyendo almuerzo, secciones y horarios individuales, y promedia el ciclo
de dos semanas. Para calendarios flexibles usa las horas de jornada completa
configuradas en el calendario nativo. Se conserva el truncado entero del
denominador legado. Un calendario sin horas positivas produce un error
explícito; no se fabrica una tarifa cero ni se inventa una jornada estándar.

`step_hr` 18.0.1.8.0 depende del núcleo. Conserva en un puente los dos campos
`hr.salary.custom.payslip_run_id` y `struct_id`, sus modelos Enterprise reales,
sus columnas y valores. El envío legado a remuneraciones también permanece
allí, con sus controles en vistas heredadas. El núcleo Community no expone
ese botón ni simula lotes o estructuras salariales.

Esta extracción no reemplaza el motor de Nómina ni certifica su exportador
legado de entradas de trabajo. Este último aún utiliza identificadores
numéricos de tipos de entrada y necesita su propia migración y aceptación.
No se invoca el envío a remuneraciones ni se recalculan liquidaciones pagadas
durante los ensayos del paquete. Las tarjas contabilizadas conservan la guarda
original de sus cómputos; las pruebas comprueban esa conservación.

## Consumidor Movilización

`step_mobilization_agriculture` 18.0.1.1.0 consume el núcleo laboral en lugar
de `step_hr`. Mantiene fundo, fecha, empresa y tipo propio en la selección de
tarjas. Resuelve por empleado las mismas relaciones a centro analítico y
producto/labor, conservando la primera coincidencia según el orden original.
La actividad de `product.template` ya es una cuenta analítica nativa; no se
sustituye por el maestro de actividades de Maquinaria.

El lookup lee las relaciones actuales en cada costeo. No conserva un caché
local que pueda quedar obsoleto después de cambiar el alcance del viaje o
la distribución de la tarja. No modifica viajes, costos o asientos históricos.
Las pruebas abarcan costeo/contabilización balanceada, nueva distribución,
empleados sin tarja, separación por fundo/fecha/empresa y la restricción que
impide borrar un fundo con viajes. El núcleo de Movilización conserva sus
perfiles y reglas por empresa.

## Aceptación y pendientes

`validate_agriculture_core.py --profile labor` contiene los dieciséis módulos
del perfil operacional anterior y tres módulos laborales/de Movilización.
En Community omite `step_hr`; en Cerro instala los núcleos faltantes y actualiza
los consumidores instalados en una copia nueva, sin desinstalar Enterprise.
Además de los contratos anteriores, compara tarifas, relaciones M2M,
metadatos de relaciones y restricciones FK/SQL del dominio laboral.
Solo se permite el cambio de propietario declarado de esas siete relaciones.
Los cachés web regenerables mantienen la excepción estricta ya documentada.

Las pruebas usan empleados y contratos desechables y secuencias de una empresa
de fixture. Los contratos de fixture empiezan en el mes actual para no generar
asignaciones acumuladas de vacaciones del motor Simple Digital. No se desactiva
ese motor ni se amplían permisos para evitar sus controles. En Community,
el verificador usa un perfil de negocio temporal; los derechos del administrador
de configuración no implican derechos de Movilización. En Cerro utiliza un
usuario existente. Las comprobaciones nativas omiten el tipo
explícito al crear sus registros temporales para no consumir los correlativos
del cliente; la numeración automática se prueba en los fixtures aislados.
Las altas nativas se revierten. No se generan liquidaciones ni emisiones SII.

Los resultados aceptados y rutas de evidencia se registran en
`COMMUNITY_CONTINUACION.md`. No usar un ensayo fallido como aceptación.
No se despliega automáticamente este paquete en Desarrollo o QA-Cerro.
La cuenta `210233` permanece descontinuada, el override bancario legado
permanece en HR y no se modifican los límites visuales de Calendar.

Siguen pendientes la frontera de Cosecha y sus consumidores, los demás módulos
que aún dependen de HR/Nómina, Simple Digital compatible, DTE, Calidad y el
ensayo de conversión integral. La base productiva conserva Enterprise;
esta extracción no resuelve el vencimiento del 31 de octubre.
