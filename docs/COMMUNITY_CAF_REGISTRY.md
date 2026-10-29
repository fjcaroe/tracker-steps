# CAF: contrato pasivo de registry

Complemento independiente del preflight `c92ef0a`. No modifica aquel auditor,
sus resultados privados ni el addon CAF criptográfico ya aceptado.

`tools/community/caf_registry_contract.py` expone `inspect_registry(env)` para
un registry privado **ya cargado por el coordinador**. No arranca Odoo, no abre
conexiones, no busca registros ni escribe resultados. Comprueba el nombre de
base privada, coincidencia cursor/registry, registry listo y transacción
READ ONLY. Rechaza producción y QA-Cerro antes de ejecutar SQL. Su única
consulta es `SHOW transaction_read_only`; las demás lecturas son metadata del
registry existente, mediante `registry.models` y clases/campos, sin `env[model]`.

El informe conserva `_table`, `_auto`, `_transient` y atributos de `_fields`:
tipo, store, required, readonly, related, grupos, nombre del compute y, para
Binary, attachment. Si `caf_file` es binary/store/attachment=True sobre el
modelo y tabla originales, `binary_attachment_policy_proven` es true: confirma
la política configurada del campo, no su contenido ni preservación de archivos.

Los proveedores se enumeran por MRO y `__dict__`; solo se describen sus métodos
declarados y firmas por nombres/tipos de parámetros. Se omiten cuerpos,
bytecode, constantes, annotations y defaults. Las firmas se obtienen de
conteos/nombres de parámetros del objeto función, sin `inspect.signature`,
`getsource`, descriptores o ejecución de métodos. Los wrappers se recorren
pasivamente con límite y detección de ciclos. No se imprime repr de callables.

Uso dentro del shell privado que ya preparó el coordinador:

```python
import importlib.util
spec = importlib.util.spec_from_file_location('caf_registry_contract', tool_path)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
report = helper.inspect_registry(env)
# El coordinador guarda report como JSON privado fuera del checkout.
```

El coordinador conserva snapshot SQL antes/después y valida la preservación.
Este helper no activa ni altera el modo de transacción: falla si no se preparó
READ ONLY. Tampoco rellena modelos ausentes en Community.

`python tools/community/caf_registry_contract_test.py` prueba aislamiento sin
Odoo/base: rechazo de producción/QA y READ WRITE; registry ausente o ajeno;
identidad de tabla; campos/compute/grupos; firmas sin defaults sensibles;
classmethod/staticmethod; wrappers cíclicos; MRO; cero ORM/records; metadata
intacta. Los proveedores sintéticos lanzan error si se ejecuta cualquier método.

Antes de la ejecución del coordinador no se afirma confirmada la política del
registry real. Los resultados mantienen `adoption_ready` y
`folio_allocation_ready` en false. Persisten asignador/concurrencia, aceptación
de payload/histórico/permisos, ancla oficial y CAF real. Este bloque no asigna
folios, no firma/emite DTE y no resuelve la conversión integral ni el 31.
