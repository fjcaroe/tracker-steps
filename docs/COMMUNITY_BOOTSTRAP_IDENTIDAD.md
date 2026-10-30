# Identidad original: checkpoints fríos y anclaje privado

Base de trabajo `a983b501`, inventario fresco S 30-10-2026 10:59:39 UTC sin
cambios. Herramientas de preparación; no importan ni adoptan registros, no
reservan números, no ejecutan DDL/DML, no cargan Odoo ni cambian la aceptación R3.

## Colisiones observadas, sin reasignación

Se comprobó el recibo de la referencia fría C antes de consultar su nombre real:
`COMMUNITY_PAYROLL_API_ORIGINAL_BOOTSTRAP_CONTRACTS_20261030C`. Su recibo SHA256
es `d4a9ec37225a3d79fff3cf426f81f43f2249e8640d356892eaed056698b5a6fd`.
Instaló 94 módulos/cero EE/sin demo y conserva cero estructuras/reglas/categorías.
No es una base donde se puedan escribir originales sin resolver colisiones:

- Acción 462: `hr_holidays.hr_leave_allocation_action_all`, de tipo
  `ir.actions.act_window`. No se puede sustituir por un reporte.
- Los cuatro aliases canónicos de tipos existen y conservan modelos/res_id y
  `noupdate=True`, pero tienen PK de metadata 41042–41045. Los PK originales
  41750–41753 están ocupados por productos legítimos de `hr_expense`.
- 21 de los 91 PK de aliases capturados tienen ocupantes; tres de esos 91 son
  aliases nuevos de referencia, no originales. El contrato original sigue
  teniendo 88 aliases de maestros, además del alias separado del reporte.
- El modelo original `hr.payslip` tiene metadata PK 600; C lo tiene en 645.
  Una acción con `binding_model_id=600` requiere que 600 sea realmente ese modelo,
  no basta con que su campo textual `model` diga `hr.payslip`.

La cápsula C fijada SHA256
`14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140`
contiene 120 maestros, 71 reglas y 91 aliases clasificados como 88+3. No se
exportan fórmulas ni valores empresariales a la salida del planificador.

`plan_original_payroll_bootstrap.py sources` inspecciona manifiestos/datos
LGPL/AGPL sin ejecutar Python. Conserva orden de archivos y calcula solamente
el mínimo de dependencias por profundidad/nombre. No afirma haber reproducido
auto-install ni asignaciones numéricas. En el runtime oficial, `-i` no fija el
orden de carga; la instalación observada F llega a `hr_contract` en el puesto
58 y a `payroll` en el 82. Un hook dependiente de Simple Digital llega tarde.

Una alternativa fría a medir es instalar sólo `payroll`, sin demo, con el
derivado NUMERIC desde su primera inicialización; después hacer checkpoint
SELECT antes de añadir `account`, Simple Digital o consumidores. Su mínimo
de dependencias tampoco demuestra por sí mismo que 462/600/88 PK estén libres.
La acción original completa sólo puede adoptarse cuando existan todos sus
extremos reales y el renderer Community; no se autoriza placeholder temprano.

El subcomando `checkpoint` exige recibo/base exactos y cápsula sellada, consulta
dos snapshots SELECT read-only iguales, clasifica ambos lados de cada alias
(PK y nombre), binding real, acción, semillas y estados de módulos. No llama
`nextval`/`setval` ni devuelve importes o fórmulas. Un espacio numérico despejado
sigue sin autorizar importación, valores, relaciones, ACL o conversión.

## Por qué el sandbox anclado necesita protección antes de arrancar

La estrategia coordinada prioriza una nueva copia íntegra de Cerro: conserva
600/462/88 PK de metadata y todos los maestros, y prueba el relevo de proveedor
sólo para la cohorte de nómina. Los demás productos no se declaran operativos.
Cambiar estados de módulos exclusivamente en esa copia no equivale a uninstall.

Fuentes LGPL oficiales inspeccionadas en el pin
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`:

| Fuente | SHA256 | Efecto observado en el código |
| --- | --- | --- |
| `odoo/modules/loading.py` | `592bd32047511963a9e9ab0c64f66afe393861f54aef3e265464784499e02071` | Procesa estados marcados, limpia namespaces procesados y ejecuta uninstall si hay `to remove`. |
| `odoo/addons/base/models/ir_model.py` | `43bfd1ebb04688fdb8013f2e941a4c9f39f69a9b4e8ab0d406683908e2ae5b6e` | Reflexión upsert por modelo o `(modelo,campo)` conserva PK pero puede reescribir metadata; `_process_end` puede borrar aliases/registros. |
| `odoo/addons/base/models/ir_module.py` | `6c8d748701681db35e9cf3c2722c3ec4df8f7fbb0b4b147896314ad918470613` | El dominio normal carga instalados; `module_uninstall` borra datos antes de marcar uninstalled. |
| `odoo/models.py` | `d978173f4a1a3f0702b081451ecc2936a1cc8d40fddcbe1043a277c0a566c86a` | `_auto_init` modifica schema y puede programar cómputos de columnas nuevas; `_check_removed_columns` retira NOT NULL de campos no registrados. |

No se leyeron cuerpos OEEL. La ausencia del proveedor original en el registro
no borra automáticamente su namespace, pero tampoco vuelve inocua la instalación
OCA. Nunca usar `to remove`, uninstall API ni defaults sobre históricos.

El caso concreto de `_process_end` son los dos aliases Simple Digital originales
con `noupdate=False` omitidos por el perfil sin semillas:
`structure_type_chile` (metadata 58549, tipo 5) y `structure_chile` (58550,
estructura 4). Los otros 59 aliases de maestros de ese namespace son True;
no se afirma que los 61 tengan el mismo riesgo de limpieza. Los namespaces
nativos no procesados no se seleccionan por ese método, salvo otras rutas.

## SQL de guardas, ejecución exclusiva del coordinador

`build_original_anchor_guards.py` genera un archivo SQL privado y su recibo,
sin conexión a PostgreSQL. Exige el anclaje real de los 88 aliases, reporte y
binding. No adopta los tres aliases nuevos de referencia. El coordinador debe
capturar antes su identidad completa, comprobar hashes/source witnesses, revisar
el SQL y ejecutarlo bajo lease en la copia nueva con respaldo.

El SQL es una transacción y se ata al nombre privado exacto. Rechaza `to remove`
y que falten filas originales. Crea funciones/triggers con nombres nuevos (sin
`OR REPLACE`) que abortan DELETE/TRUNCATE o cambios de las claves originales:

- `ir_model_data`: todos los PK originales del anclaje, módulo/nombre/modelo/
  res_id/noupdate; no convierte False en True.
- `ir_model`, `ir_model_fields`, selecciones: PK y claves de modelo/campo/valor/
  estado; no congela etiquetas, help, tipos o required que el relevo debe admitir
  individualmente en su contrato de metadata.
- Los 120 maestros: todos sus valores en columnas originales, incluidos NULL y
  auditoría. Una columna OCA nueva nullable no da permiso para tocar las previas.
- Todas las columnas originales de la acción 462 (desde el catálogo sellado de
  la fuente) y sus pares de grupos: no renumera ni cambia renderer/attachment.

La guarda **aborta**, no omite un unlink ni devuelve éxito falso. Un fallo debe
conservarse y resolverse con propiedad/retención explícita admitida. Retener un
alias False mediante `loaded_xmlids` sólo es válido tras verificar modelo,
registro y proveedor real; no se implementa una retención global a ciegas.

`retain_original_bootstrap_aliases.retain_original_aliases(env, *, capsule_path,
capsule_sha256, original_identity_path, original_identity_sha256)` proporciona
esa retención exacta de los dos aliases anteriores. Su única mutación es al
set real `env.registry.loaded_xmlids`. Exige cápsula C fijada, ambos archivos
privados 0600/hash exacto, base clonada, cero EE/motores nativos activos y ningún
`to remove`; comprueba MRO real OCA/oficial, modelos persistentes y sus tablas,
PK/modelo/nombre/estado de metadata, binding/noupdate de ambos aliases y la
proyección PostgreSQL exacta de todas sus columnas originales (NULL/auditoría
incluidos). JSON original se interpreta en PostgreSQL, sin conversión numérica
por Python. Todas las comprobaciones son SELECT, sin ORM de históricos.

Debe llamarla el addon admitido del coordinador **antes** del `_process_end`
real, una vez presentes los proveedores; un post-init del addon posterior a
Simple Digital puede servir para el primer ensayo. Si cualquier comprobación
falla, no se añade ninguno de los dos aliases. Para posteriores actualizaciones
de esos namespaces hay que volver a ejecutar la comprobación antes de limpiar;
un post-init ejecutado sólo una vez no certifica esa continuidad. No se añaden
aliases de propiedad ficticios ni se altera False a True para conservarlos.

**Límites:** los tests puros verifican generación, no ejecución de triggers en
PostgreSQL. El coordinador debe probar savepoint, intento real DELETE/retarget/
noupdate y rollback en su copia antes del primer Odoo. Los triggers no protegen
DROP/ALTER, cambios en las demás propiedades de metadata ni toda la historia.
El diff de schema, los snapshots completos, los importes/correlativos, las ACL
y el testigo posterior siguen siendo obligatorios. Una mezcla de metadata
nativa con motor OCA no constituye por sí sola una conversión aceptada.

No hay cambio de producción, QA, vencimientos ni liquidaciones. El anclaje de
cohorte, su cálculo aprobado y sus pruebas funcionales todavía deben ejecutarse
con el paquete exacto por el coordinador.
