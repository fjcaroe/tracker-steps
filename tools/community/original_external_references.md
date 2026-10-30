# Clausura readonly de referencias originales

Herramientas propias. No importan maestros, conceden permisos, cargan registros
ORM, evalúan reglas, reservan/renumeran IDs ni ejecutan DDL/DML. Sólo el caller
coordinador puede cargar el registry privado bajo su lease y acreditar que
conserva todas las tablas/contadores. No se inspeccionan cuerpos OEEL.

`original_external_references_registry.inspect_registry(env,
source_packet_sha256=..., acceptance_sha256=...)` requiere un registry privado
ya cargado y transacción READ ONLY. Recorre clases/Field metadata: tabla real,
herencia, M2M tabla/columnas/inversa, referencia/discriminador y propiedades
JSON. No obtiene tablas mediante `model.replace('.', '_')`, llama selections
dinámicas ni lee campos de registros. Captura también el tipo, almacenamiento,
compute/related del discriminador; una columna SQL legacy no prueba por sí sola
un discriminador almacenado. Véase el contrato libre de
[Many2oneReference oficial](https://github.com/odoo/odoo/blob/18.0/odoo/fields.py).

El CLI `original_external_references.py` exige cápsula C exacta `14b18ced…`,
prueba de registry, `--runtime-proof` del launcher readonly revisado,
aceptación completa H/D, postflight de módulos y backup
privado `source.dump`. Primero hashea los bytes reales del respaldo y detecta
cambio de archivo. `pg_restore --data-only --schema=public
--table=ir_model_data --file=-` extrae únicamente metadata COPY. Su texto es
inerte: nunca se carga/restaura ni ejecutan COPY, setval o comandos del dump.
Se decodifica mediante el parser COPY ya versionado y se comparan los seis
campos de TODOS los XML IDs con el identity-before del respaldo propio. No se
fija un conteo viejo de XML IDs. Después clasifica 88 aliases originales de
configuración y tres del adaptador; añade el alias original del reporte462.
Los tres del adaptador no se convierten en PK originales que reservar.

El catálogo PostgreSQL demuestra PK/unique no nullable y FK reales. El plan
enumera relaciones físicas con claves completas del dueño y extremos
modelo/tabla/columna/ID; una M2M conserva sus dos columnas y sus FK, no sólo
un count. Comprueba la familia completa PG de acciones y sus modelos de
registry, incluidos los consumidores del ocupante actual de462. Captura
ocupantes PK y aliases nominales, sin seleccionar un ID de reubicación.

Se observan todas las referencias entrantes a los 120 maestros y a la familia
del reporte, y las salidas originales —incluidos diarios/compañías, usuarios de
auditoría, calendarios y metadata del reporte—. Los demás maestros son extremos
externos, no objetivos adicionales de adopción/renumeración. Las propiedades
Many2one por compañía se leen por cada clave JSON, con NULL conservado, dueño
PK, compañía e ID de destino; formas malformadas u orfandad bloquean.
Reference y Many2oneReference requieren modelo explícito/discriminador real;
un entero coincidente no se convierte en vínculo. Los endpoints incluyen
ocupante físico, hash de fila y aliases, ligados al campo y dueño que los
refieren. No se exportan nombres personales ni fórmulas o importes salariales.

JSON sin esquema relacional y configuración serializada (vistas, dominios,
contextos, defaults, código de acciones, parámetros) permanecen como candidatos
**sin binding semántico**. Se conservan clave del dueño y hash opaco; no se
ejecutan ni se interpreta un número como prueba de pertenencia. Las filas
no vacías, modelos ausentes, vistas calculadas, discriminadores no almacenados
o computados, FK incompletas/ambiguas y aliases no adoptados mantienen el bloqueo.

Se repiten snapshots READ ONLY por socket Unix, sin credenciales heredadas.
Cambiar un catálogo, alias, módulo, referencia o endpoint entre fases aborta.
El informe incluye consultas SELECT y observaciones completas para recompilar
y revalidar desde código Git confiable dentro del futuro lock/transacción del
escritor. Contiene hashes del backup, aceptación, packet, registry y herramientas.
No ejecutar Python/SQL de artefactos como si fuera código confiable.

El recibo runtime es obligatorio: liga los bytes exactos de las herramientas
aprobadas, aceptación/packet, registry, todos los snapshots públicos y cada
cursor real de Odoo. `PGOPTIONS` aislado no basta: Odoo fija la política de su
pool al conectar. El launcher inspeccionado la obliga readonly **antes** de
cualquier conexión, conserva `cr.readonly=True` y comprueba `SHOW` real. La
lectura de señalización sustituye únicamente el método LGPL fijado por hash
por su SELECT real contra el primario local, con las cinco claves de cache
originales. No altera setup/signals/nextval ni fuentes instaladas; cualquier
escritura aborta. Para la inspección nativa se exige el CLI oficial sin el
finalizer del runner de upgrades. Los intentos abortados no son capturas
aceptadas aunque sus tablas y secuencias permanezcan intactas.

`reference_closure_ready` se limita a los bindings capturados. El informe nunca
autoriza importar o reservar IDs y no acredita seguridad, actor normal ni
conversión del motor. Las pruebas funcionales de adopción corresponden al
coordinador sólo después de cerrar las puertas reales. Ni este informe ni una
coadopción parcial resuelven el vencimiento o habilitan producción.

Pruebas sin base: `python -m unittest test_original_external_references
test_original_external_references_registry test_original_external_references_dump`
desde tools/community. Las pruebas SQL sintéticas adicionales se ejecutan sólo
con SELECT/READ ONLY en copias aceptadas y no constituyen adopción de maestros.
