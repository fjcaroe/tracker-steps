# Etiquetas contables originales en la preparación OCA

El bloque conserva `hr.salary.rule.debit_tag_ids` y `credit_tag_ids` como
Many2many reales a `account.account.tag`, almacenados, copiables y editables.
Usa exactamente `hr_salary_rule_debit_tag_rel` y
`hr_salary_rule_credit_tag_rel`, con columnas `hr_salary_rule_id` y
`account_account_tag_id`. El origen tiene PK compuesta, ambos extremos NOT NULL
y FK CASCADE. Las dos relaciones están vacías en la referencia Cerro F.
No se inventan maestros ni se sustituyen relaciones por texto.

La herencia clásica OCA se cierra con overrides explícitos en `hr.payslip.line`:
ambos campos son calculados, readonly, no almacenados y no copiables, como el
contrato de metadata observado. No reutilizan la relación del maestro con IDs
de líneas ni crean una tabla histórica paralela. Son una proyección de la
configuración actual de la regla; las etiquetas históricas financieras son
las almacenadas en `account.move.line.tax_tag_ids`, no esa proyección.

## Semántica observada y ejecución real

Se auditó el proveedor LGPL OCA `payroll_account 18.0.1.0.6` y los modelos
Account de Community oficial `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.
El probe privado B ejecutado por el coordinador sobre el proveedor nativo real
observó cuatro combinaciones de signo y solicitud de `credit_note`. Las
etiquetas de débito permanecieron en la cuenta configurada como débito y las
de crédito en la cuenta configurada como crédito, incluso cuando el importe
negativo intercambiaba el signo contable de ambas líneas.

La implementación propia aplica esa asignación a los dos preparadores reales
OCA mediante `super`. Une los IDs originales con las etiquetas ya devueltas
por OCA, sin borrar estas últimas, duplicarlas ni crear/modificar sus maestros.
Conserva importes, cuentas, impuestos, reparticiones e inversión fiscal del
proveedor. La confirmación y publicación siguen siendo las operaciones reales
OCA y Account; no existe un asiento o motor simulado.

No se afirma equivalencia monetaria de los reembolsos nativos con OCA.
OCA invierte expresamente el importe cuando su `credit_note` real está activo.
El probe nativo C confirma que su bandera efectiva permanece True antes/después
de confirmar y **no invierte el importe** en esos fixtures. Los cuatro asientos
nativos conservan `tax_tag_invert=False` y etiquetas por cuenta configurada,
igual que la aplicación de etiquetas CE. Se observó también que los cuatro
campos nativos no declaran un dominio: la restricción CE a etiquetas fiscales
activas/país compatible es una frontera de admisión propia más estricta,
no una supuesta regla o dominio nativo.

C se ejecutó offline en una copia nueva, con Unix socket PostgreSQL y contexto
de pruebas real, sin leer cuerpos OEEL. Sus observaciones y la pareja final
permanecen en la evidencia del coordinador. Este bloque no cambia la semántica
de reembolsos para hacer coincidir artificialmente importes de dos motores;
la equivalencia del flujo nativo de notas de crédito continúa pendiente.

## Permisos y preservación

La admisión de contabilización comprueba reglas efectivas y todas las reglas
de líneas ya calculadas. Para cada relación lee primero ACL de regla/campo,
luego los pares físicos completos y el acceso normal a cada etiqueta. Un
record rule que oculte sólo una contribución no produce un asiento parcial.
Ni `sudo` entrante ni una caché caliente sustituyen al actor original.

Las etiquetas originales no vacías deben estar activas, aplicarse a impuestos
y tener el país fiscal de la liquidación o país vacío compartido. Una relación
incompatible se conserva y bloquea la operación; no se limpia, reasigna o
repara al leer. Los comandos del resultado del preparador sólo pueden unir
relaciones; un comando que altere maestros o un ID inválido aborta. La
preparación revisa también permisos de crear líneas y escribir `tax_tag_ids`.

La guarda ya existente mantiene la confirmación en un savepoint. Un fallo
temprano o tardío no deja cambios de estado, importes, líneas o asientos aunque
el llamador capture la excepción. Leer/mostrar historia cerrada no ejecuta la
admisión de contabilización ni reconstruye importes desde el sueldo vigente.
Cambiar etiquetas de una regla no reescribe las del asiento publicado.

Una extensión XML propia sobre la vista LGPL de OCA muestra cada relación
junto a su cuenta. El usuario selecciona maestros existentes; la vista no
crea etiquetas ni concede roles. No hay menús alternativos o fuente OEEL.

## Wiring y validación

El coordinador importa `models.original_account_tags` y
`tests.test_original_account_tags`, y añade
`views/original_account_tags.xml` al manifest de la versión que acepte.
No hace falta una proyección DDL: el ORM real conserva una tabla M2M ya
existente y sus pares. La adopción integral debe cerrar todavía los IDs de
campos y maestros, propietarios de relaciones y referencias externas; no se
retargetean aliases ni se importa sobre los maestros demo de Community.

Ocho pruebas funcionales nuevas cubren formulario, columnas/FK/pares,
cuatro combinaciones de signo/credit note, posting y fiscal inversion reales,
unión de una etiqueta devuelta por la preparación tributaria OCA real,
ACL de fila/campo con caché y sudo, compañía/país/aplicabilidad/archivo e
históricos publicados. La prueba de unión no certifica una declaración de IVA
ni reemplaza la certificación chilena integral. El payload de observación
nativa tiene rollback obligatorio y se ejecuta únicamente por el coordinador
en una copia privada bajo las barreras operativas; nunca contra F o producción.

Este documento describe el alcance del código. La aceptación exige el paquete
exacto en Community oficial y copia fresca de Cerro, snapshots y evidencia
independiente. El bloque no convierte integralmente el motor ni resuelve la
fecha del 31 de octubre.
