Este auditor no convierte datos ni carga Odoo. Captura dos veces, en PostgreSQL
READ ONLY y con entorno limpio después de `sudo`, los cuatro campos originales:
nombre literal de línea, nombre traducido de regla, nombre nullable de días y
calendario nullable de contrato con FK `SET NULL`. Sólo consulta catálogos y
metadata de módulos instalados; no consulta liquidaciones, reglas de cálculo,
importes ni maestros de negocio.

```sh
python audit_payroll_history_storage.py capture --database PRIVATE_CLONE \
  --profile normal-community --output /absolute/private/new-storage.json
python audit_payroll_history_storage.py compare --source native-storage.json \
  --target new-storage.json --output /absolute/private/new-comparison.json
```

`PRIVATE_CLONE` debe tener uno de los prefijos privados admitidos en el código.
Los perfiles son `normal-community`, `anchored-community` y `native-reference`.
Community requiere OCA/API instalados y cero Enterprise. Sólo el perfil
anclado compara identidad literal de modelos/campos/aliases con la fuente;
una instalación nueva nunca se presenta como preservación de IDs originales.

El coordinador puede llamar `inspect_registry(env)` dentro de su bootstrap
readonly ya aceptado. La función sólo lee `_fields` y confirma `SHOW
transaction_read_only`; no ejecuta computes, defaults, métodos del proveedor
ni lecturas ORM. `assess(catalog, runtime)` contrasta ambas observaciones.
La CLI de catálogo conserva `runtime_metadata_match=None` hasta recibir ese
testigo real, sin inferirlo de `ir_model_fields`.

Las cinco pruebas funcionales de `HistoryStorageCases` se ejecutan mediante
wrappers explícitos en API y referencia nativa, con actor normal y fixtures
privados. No calculan, cierran ni pagan liquidaciones. No hay excepción para
las demás columnas, metadata semántica, históricos o diferencias de la copia
integral; `adoption_authorized` e `integral_conversion` permanecen falsos.
