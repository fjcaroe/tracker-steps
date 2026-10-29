# Preservación de XML IDs financieros y su ciclo de carga

Los 15 aliases originales de BancoEstado/Security y los 37 de Multimoneda
conservan la misma fila de `ir.model.data`, namespace, nombre, modelo,
`res_id` y bandera `noupdate`. La adopción añade otro propietario real en
el núcleo Community; no convierte una bandera original falsa en verdadera.
En Community limpio sólo existen 13 aliases bancarios si falta el proveedor
real del wizard bancario relacionado. No se crea un sustituto de ese modelo.

## Carga y limpieza

Se revisaron `odoo/addons/base/models/ir_model.py` y
`odoo/modules/loading.py` del checkout oficial Community
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.

Odoo `_load_xmlid` marca un identificador ya existente en
`registry.loaded_xmlids` sin escribir su bandera. `_process_end` conserva los
identificadores marcados. Un identificador falso no marcado puede perder su
fila aunque otro namespace siga conservando el registro al que apunta.
Los hooks de adopción y post-init usan esa API después de comprobar la
identidad del alias y el propietario Community exacto.

Una actualización posterior sólo del bridge no vuelve a ejecutar los hooks
del núcleo. Por eso ambos núcleos extienden únicamente `_process_end`: si se
procesa su namespace legado conocido, revalidan sus campos, selecciones,
modelos y vistas reales, y marcan sus aliases antes de delegar a `super`.
No retienen identificadores ajenos a ese contrato ni cambian la política de
limpieza del resto de módulos. La comprobación del proveedor vivo ocurre
después del setup; pre-init valida la identidad persistida porque Odoo lo
ejecuta antes de `registry.load(core)`.

## Retiro de un namespace

El mecanismo nativo `_module_data_uninstall` conserva un registro que posee
otro XML ID fuera de los módulos que se retiran. Esa protección procede del
propietario independiente Community, no de la bandera `noupdate`.
Al retirar deliberadamente un namespace se eliminan sus propias filas de
aliases; este bloque certifica retención del registro, su ID y sus valores
mediante el propietario Community. No autoriza desinstalar módulos en un
ambiente activo ni acredita la conversión integral de Enterprise.

## Upgrade y evidencia

Los nuevos niveles son `step_bank_export_core 18.0.1.2.2` y
`step_accounting_multicurrency_core 18.0.1.1.1`, con pre/post-migraciones para
instalaciones existentes. No se intenta reparar heurísticamente una bandera
ya cambiada por un ensayo anterior: sin el testigo original no puede inferirse
si un `True` era legítimo. Los ensayos nuevos parten de la fuente intacta.

Se amplían los métodos funcionales existentes sin aumentar el conteo: mezcla
de flags originales falsos/verdaderos, hooks repetibles, dos limpiezas reales
consecutivas del bridge sin ejecutar de nuevo los hooks y retiro nativo de un
namespace privado falso con propietario Community. Se comprueban también
los valores bancarios y monetarios. `finance_frontier_contract` exige ahora
igualdad exacta de la metadata bancaria; el testigo integral de preservación
no recibe normalizaciones ni exclusiones. Las pruebas de la pareja exacta y
su aceptación corresponden al coordinador.

Aceptación: pareja F de [COMMUNITY_PROPIEDADES_NOMINA.md](COMMUNITY_PROPIEDADES_NOMINA.md),
375/252 casos sin fallos, preservación exacta de los 59.048 XML IDs originales
con noupdate y de los 52 aliases financieros descritos aquí.
