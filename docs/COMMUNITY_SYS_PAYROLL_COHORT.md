# Nómina de SyS sobre Community

La prueba de octubre de 2026 arranca Odoo 18 Community con OCA Payroll sobre una
copia privada de SyS. El asistente de Previred produjo el mismo TXT v98 que la
referencia nativa de SyS. Los cinco trabajadores admitidos tienen AFP positiva
conciliada con sus líneas originales. Cada fila contiene 105 campos y se
reprodujeron los dos avisos sobre asignación familiar. No hubo anexos ni descartes.
El Libro de Remuneraciones reproduce asimismo las cinco filas, 147 columnas y
SHA-256 `38d10fe52f0b1d41084e86658d33cd2fdbd44d783eeb8bdaf6005992e65f5009`
de la exportación nativa. Ambos archivos de Previred tienen SHA-256
`10c69a74a4454f468acc8040f8fe60ea2361fc9003618f62dbbd071932622dd6`.

## Alcance del arranque

El ensayo con las 336 declaraciones originales mantuvo el grafo restaurado.
El registro oficial Community arrancó sin los modelos de liquidación y del
asistente. Para ensayar el flujo de nómina se restauró una segunda base con
los 2.678 objetos verificados del filestore original. El plan privado registra
las 157 declaraciones apartadas por falta de proveedor admisible, incluidas
las dependientes. Los 142 módulos con licencia OEEL conservan su declaración
original en la base de referencia. La aceptación integral de los demás
productos de SyS sigue pendiente.

En esta cohorte de nómina, el registro usa el proveedor AGPL de Simple Digital
que correspondía a SyS, los proveedores propios y los módulos libres de
Community/OCA. El cierre de dependencias de Previred y de Nómina se comprueba
antes de instalar el motor. Los XML IDs de estructuras, tipos, usuarios,
grupos y datos de nómina siguen perteneciendo a sus registros originales.
La preparación permite a las nuevas referencias OCA de los grupos de nómina
resolver los dos grupos existentes. Las listas de control y las relaciones
originales de usuarios, grupos y reglas están protegidas durante la carga.

La relación de estructura con reglas de SyS es uno a muchos por
`hr.salary.rule.struct_id`. Las 92 reglas pertenecen a cuatro estructuras.
Los consumidores SQL de la interfaz OCA leen una vista de esa FK en tiempo
real, sin duplicar ni asignar reglas. El diario de liquidación sigue la
propiedad de la estructura según la empresa. Las líneas históricas no se
recalculan al introducir el padre opcional de línea de OCA.

U40F repitió la restauración y el arranque desde el respaldo completo.
Se conservaron todas las columnas originales de las 25 tablas, incluidos los
18 requisitos NOT NULL, las 298 llaves foráneas y los 111 contadores. Los
53.659 XML IDs originales conservan su contenido y los 694 nuevos ocupan IDs
posteriores. El operador verificó los siete campos obligatorios de nómina,
la lectura de las 92 reglas y los diarios de las cinco liquidaciones. Volvieron
a coincidir los archivos de Previred y del Libro de Remuneraciones.

## Campos de empleados y contratos de SyS

En U40S se comparó primero el respaldo con la referencia nativa del paquete
`0f677fc2`. Los dos módulos `step_sys_hr_fields` y
`step_sys_hr_simpledigital_views` se instalaron mediante el cargador nativo
antes de congelar las filas de metadatos. La preparación conserva el límite
original de los XML IDs y protege además las nuevas identidades que registraron
los dos módulos. La restauración de origen y el ejercicio Community se
ejecutaron en la misma derivada privada con las liquidaciones cerradas protegidas.

El operador de la empresa 37 vio la categoría y el tipo de contrato en la lista
de empleados y el porcentaje de cotización en el formulario contractual. Los
dos entornos preservaron valores, identificadores, vistas y permisos. El operador
creó un empleado y un contrato temporales, utilizó ambas relaciones y modificó
el porcentaje. La escritura del usuario público fue denegada. Ambos ensayos
revirtieron los registros temporales y produjeron el mismo recibo
`398513320a03d1a4c406c2127aafc1515777eb75cfd7e202f7afb856225f4e71`.
El TXT v98 volvió a coincidir con el original. El postflight conservó las 25
proyecciones, la forma de todas las columnas originales, 298 llaves y 111
contadores. Se protegieron los 53.668 XML IDs presentes tras la adopción y
se verificaron individualmente todos los 53.659 de la referencia anterior.

## Reproducción

1. Restaurar en una base privada la pareja de SQL y filestore sellados de
   SyS. Generar la referencia nativa con el asistente real. Los archivos con
   contenido laboral quedan en el archivo privado de evidencia.
2. Obtener el inventario desde la fuente real con
   `probe_sys_community_graph.py`. Completar la admisión física y la protección
   de cabeceras y detalles cerrados con `admit_sys_payroll_storage.py` y
   `guard_sys_payroll_history.py`.
3. Sobre otra derivada, aplicar `prepare_sys_payroll_cohort.prepare` y conservar
   su plan privado. `build_sys_payroll_cohort_profile.py` prepara los dos módulos
   libres, las relaciones originales y los manifiestos privados contra las
   huellas revisadas de origen. El código privado del proveedor chileno se
   deriva de su propia versión de SyS.
4. Mantener el bloqueo operativo, el registro sin red, HTTP ni cron y las
   rutas privadas durante la instalación. Encolar los módulos propios por el
   botón de instalación y usar `load_sys_payroll_cohort.py` con el runtime
   oficial. El cargador verifica los dos alias nativos del proveedor antes
   de ejecutar la limpieza normal.
5. Ejecutar `probe_sys_previred_wizard.py` en ambas bases y entregar sus
   registros privados a `compare_sys_previred_receipts.py --native …
   --community …`. Se exige igualdad del TXT, cohorte, importes AFP comprobados,
   diagnósticos, empresa y operador.
6. Cotejar proyecciones, identidades y FKs con `check_sys_payroll_cohort.py`.
   El Libro y el cálculo de borradores tienen comprobaciones independientes en
   `replay_sys_payroll_cohort.py`. Ningún cálculo se aplica sobre liquidaciones
   originales y no se transmiten documentos a entidades externas.

## SyS, recálculo y cierre en Community el 26 de noviembre

Se probó la restauración de SyS con el usuario de Nómina y el contexto de
cada empresa. El respaldo nativo es la referencia para los cálculos
actuales. Las liquidaciones cerradas y sus asientos se protegieron contra
escrituras durante cada prueba.

| Prueba | Resultado observado |
|---|---|
| Último mes completo por empresa | 133 liquidaciones en 12 empresas. Los dos motores calcularon 130 con el mismo código de regla, importe, cantidad, tasa y total en 2.098 líneas. Los otros tres contratos conservaron la revisión pendiente y el mismo rechazo del módulo original. |
| Comparación con las liquidaciones cerradas | 97 de los 130 recálculos reprodujeron también los valores históricos. Los otros 33 coincidieron entre los motores actuales y difieren del histórico. Se conservan los importes cerrados. |
| Cierre individual | Cada uno de los 130 borradores creó un asiento de diario en borrador, sin apuntes. En 127 casos se pudo comparar directamente la cabecera original. Tres referencias contables históricas están fuera de la empresa del operador. |
| Reglas con códigos repetidos | Cinco liquidaciones de octubre reprodujeron sus 86 líneas originales. Un sexto ensayo activó el movimiento 7. Se observó la ejecución de ambas reglas elegibles y la identidad retenida por ambos motores. |
| Exportaciones de referencia | Previred de octubre coincidió byte a byte en 5 filas de 105 campos y el Libro en 5 filas de 147 campos. |
| Impresión | La acción original 1431 generó cinco PDF con las cinco cifras líquidas originales y 61 líneas visibles. Se comprobaron las ocho versiones archivadas. |
| Alcance de acceso | Se instalaron 16 reglas y se verificaron sus 12 vínculos a grupos. Dos empleados de ensayo pudieron imprimir su propio documento. Las dos impresiones cruzadas fueron denegadas. |
| Formularios de personal | Los tres campos originales y las dos vistas de SyS conservaron sus identidades, datos y permisos después de la instalación. |

La restauración U40I instaló 190 módulos en el entorno Community oficial
sin módulos activos de licencia Enterprise. El paquete privado de siete módulos
tiene huella `1dfb442394cd732f17ccd119181ecc8f813bc0c0e2cf686bbd402438293b144f`.
El control de conservación devolvió cero diferencias en las 25 proyecciones
originales, 53.659 identificadores XML, 298 claves foráneas y 111 contadores.
El verificador contrasta íntegramente las reglas y vinculaciones originales
y comprueba individualmente cada nueva regla, dominio, permiso y grupo.
El comprobante privado de esta verificación tiene huella
`b5344158b8eb5bbcb9597502a07a28886a1496e21de9a000f040a69397a9759b`.

El cierre de las 130 liquidaciones y la prioridad del aviso de revisión
de contratos se comprobaron en una revisión posterior de U40I. Se conservó
el módulo de transición de SyS del release `1d099f7a` con su código y grupos
originales. La dependencia declarada en la edición libre establece el orden
en que se aplican su revisión contractual y los controles de configuración.
El cálculo sin entradas de trabajo admite los días de un cierre original
cuando coinciden empleado, contrato, empresa, período, tipo, días y horas
y el operador puede leer todas las líneas.

Las pruebas usan `probe_sys_company_drafts.py` y
`compare_sys_company_drafts.py --accounting --require-review-policy`.
Para el control físico de U40I se pasa a `check_sys_payroll_cohort.py` el
archivo instalado con `--employee-policy`. Es obligatorio conservar también
los registros y permisos anteriores. Los archivos privados completos de
esta etapa están en el directorio U40 del ensayo del 25 de noviembre.

El grafo completo de SyS tenía 336 módulos instalados. Esta cohorte excluyó
156 del grafo original. La conversión completa de SyS, Cerro y Steps y la
publicación en producción siguen pendientes. El plan de retención retiró
cuatro bases transitorias de Cerro de los ensayos U17, U17B, U18 y U18B,
con 727.346.256 bytes. Los controles U17D y U18C, los respaldos y los
comprobantes permanecen disponibles.

## Instalación independiente de SyS y regresión de Cerro

La copia U40J se restauró desde el respaldo original de SyS en el espacio
privado de pruebas. El paquete privado tiene SHA-256
`f9a7be026a550acf3e383f92414ed18161d6336d771184ee0936daeaf81d39e7`.
El arranque en Community oficial comprobó las versiones de los siete módulos
del paquete y 190 módulos activos. Las 130 liquidaciones calculables
volvieron a coincidir con SyS en 2.098 líneas y 130 cierres individuales.
Los tres contratos pendientes fueron rechazados por el mismo control original.
La prueba de horas aceptó la jornada guardada y rechazó el borrador después
de cambiar una hora, conservando intacta la liquidación cerrada.

El lote de octubre de la empresa de referencia pasó de revisión a cerrado
por sus botones originales, con cinco liquidaciones y cinco asientos en
borrador. La acción original de impresión generó los cinco PDF con sus
líquidos y las 61 líneas visibles, y se verificaron los ocho archivos
anteriores. El recibo independiente tiene SHA-256
`4ead793cef344643be253f136c30656e5c83ed8de933dd781a905c2535db8cd1`.

En una copia privada de Cerro se probaron los dos cambios contables comunes.
El operador abrió tres formularios y las cuatro estructuras conservaron la
relación del diario por contrato. Pasaron cinco pruebas de contabilización,
incluidos el diario inaccesible, la mezcla de empresas y el diario ajeno.
Tres estructuras conservan el diagnóstico de líquido desconectado del bruto
y una el de bruto desconectado del sueldo base. Este ensayo certifica las
regresiones contables de Cerro. La referencia de liquidaciones es SyS.

## Lotes originales de octubre en SyS

El operador de Nómina abrió el menú original 953, la acción 1426 y el
formulario 5024 en cada una de las once empresas con liquidaciones en octubre.
En la copia nativa y en el candidato creó los once lotes sin introducir un diario.
Community obtiene ese diario de la propiedad explícita de la estructura para la
empresa en uso. Los lotes históricos conservan sus valores.

En nuevos lotes se calcularon y cerraron las 130 liquidaciones del período.
Los dos motores produjeron los mismos importes y los mismos 130 asientos
en borrador, cada uno sin apuntes, tal como estaba configurado en SyS.
También se probaron la apertura de las liquidaciones desde el lote y los
cambios de estado a pagado, de vuelta a cerrado y a borrador. Esos pasos
no cursan transferencias bancarias. Dos adjuntos bancarios guardados en julio,
uno del lote y otro de una liquidación, conservaron sus 215 bytes cada uno.

El contrato de Community protege los importes de una liquidación que ya se
validó, incluso cuando su lote vuelve a borrador. El origen permite recalcular
después de reabrir. Esta diferencia se registra por separado de los 130 cierres
iniciales y de los archivos históricos. Las pruebas se ejecutaron con
transacciones reversibles en las restauraciones privadas de SyS.

## Instalación nueva con el flujo de pago y reapertura de SyS

La restauración U42L partió del SQL nativo de SyS e instaló en Community la
versión 18.0.1.6.0 de la adaptación de históricos. El calendario conservó de
origen su campo obligatorio de jornada Previred. Se actualizó el módulo por
Odoo a 18.0.1.6.1 y se comprobaron las versiones instaladas, los 190 módulos
activos y los archivos exactos del paquete. El archivo probado tiene SHA-256
`547c89989b796475cbb46075992f4008c10d23f7a50bbf450f0941192e81fc07`.

En las once empresas de octubre, el operador original creó el lote desde el
formulario habitual. En julio, el archivo bancario del lote de seis personas
y el de una liquidación individual coincidieron al byte con los del motor
nativo. Al generar el lote completo, Community guardó sus seis filas en el
lote y una fila propia en cada liquidación. El original guardaba las seis
filas en cada ficha. Se verificó también la generación individual sin lote.
En ambas versiones, la acción individual de una liquidación vinculada a un
lote también guarda ese informe individual en la ficha del lote.

Al devolver una liquidación pagada a validada, su lote volvió a cerrado y
las demás conservaron sus estados. Al reabrir y volver a cerrar el lote de
octubre, Community mantuvo los importes protegidos y reutilizó sus cinco
asientos originales. El cotejo de los formularios y botones está en
`tools/community/verify_sys_batch_actions.py`. El recibo privado de U42L
tiene SHA-256
`c881e8892b959212b019352d234093810e2328b50084e80a6213acb764f451dd`.

Las 133 pruebas de cálculo y cierre dieron los mismos resultados que las
dos copias Community anteriores. Los dos operadores también reprodujeron los
24 archivos de Previred y los 24 del Libro, todos idénticos al origen. El
recibo de exportación tiene SHA-256
`8bc17de0a65c8c2738343da7e299d8a9a8eada7f5af34a9a43b9dd6632f444db`.
Después de esos recorridos, el control de conservación de U42L volvió a
verificar las 25 proyecciones, los 53.659 identificadores originales, las 298
relaciones, los 111 contadores y las reglas de acceso admitidas. El recibo
tiene SHA-256
`69838dd5a335f5df4b1c46249ff1f8ccf4e4a38d1f0f461d9d729c989e2f745e`.

### Diferencias con los importes históricos de octubre

Se repitieron los 33 cálculos que habían diferido de la liquidación guardada,
con el mismo operador y sus permisos de empresa. U40N y U42L 18.0.1.6.1
generaron cada una 33 borradores nuevos y reprodujeron las huellas de las
líneas históricas y de las líneas calculadas del primer ensayo. Los 33 casos
pertenecen a cuatro empresas y a octubre de 2026.

| Importes distintos del histórico | Liquidaciones |
| --- | ---: |
| Solo el líquido entre los tres importes de resumen | 32 |
| Básico, bruto y líquido | 1 |
| Solo otras líneas, con básico, bruto y líquido idénticos | 0 |

Los dos motores calcularon los mismos importes en los 130 casos admitidos.
De ellos, 97 reprodujeron íntegramente la liquidación guardada. Los otros tres
casos de los 133 seleccionados volvieron a quedar fuera del cálculo en el
control original de revisión de contrato. El cotejo sumó con precisión decimal
los totales por código y distinguió la ausencia de una línea de un importe
cero. Se revirtieron las operaciones de cada borrador y se verificó que las
16 tablas de negocio conservaran sus filas completas.

Los recibos privados de los nuevos borradores tienen SHA-256
`2ff075e5b52272d1511f48cf8e8f56cb936f252123004f7806827b101482808f`
(nativo) y `b26c62c50830a79f5e0bf7310ad027b9b2304014eee7709c8bfaab8645c8063c`
(Community). La clasificación de `tools/community/compare_sys_summary_variance.py`
contra los dos recibos anteriores de 133 casos tiene SHA-256
`c54a41bdba98ed3122b920c6a118cab0ee0b8ae65fc2393976dd9ee258f51065`.

La revisión posterior comparó las identidades de las reglas y sus componentes con nueve respaldos fechados de SyS. En 23 liquidaciones, la desaparición de un crédito CCAF explica todas las líneas. Las otras diez ya constaban como editadas en el histórico. [Reglas y fuentes de las 33 diferencias](COMMUNITY_SYS_REGLAS_HISTORICAS.md).
