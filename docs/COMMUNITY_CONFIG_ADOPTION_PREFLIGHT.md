# Preflight de identidad, permisos y traducciones de configuración

Bloque de solo lectura desde canónica `db398fba`, rama propia
`codex/community-payroll-config-acl-20261029`. Complementa
`COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md`; no modifica la API de configuración ni
el reporte, no importa registros y no amplía permisos.

## Herramienta y límites

`tools/community/payroll_configuration_adoption_preflight.py` verifica la cápsula
privada C, permiso 0600, SHA256 aprobado, hashes de tablas, IDs, XML IDs y
referencias. La fuente es su copia nativa B ya existente; el destino auditado es
G, referencia Community **con demo**, no el futuro destino de importación.

Cada captura usa PostgreSQL REPEATABLE READ READ ONLY, sin Odoo. SQL devuelve
solamente hashes de filas de configuración; no devuelve cuerpos de fórmulas ni
lee liquidaciones. El JSON privado contiene hashes y metadata técnica, nunca
filas crudas de la cápsula, nombres/traducciones de reglas o código salarial.
Empresas se contrastan con huellas de nombre/RUT; no se leen contraseñas,
logins, contactos o saldos. No se evalúan reglas o dominios ni plantillas EE.

Compara schema físico y metadata de los cinco modelos; ocupación de IDs;
XML IDs aunque el destino los haya ligado a otro modelo; relaciones internas
y proyección estructura/regla; propiedades JSON completas por compañía;
extremos externos y tipo de acción del reporte. Compara ACL efectivas por
XML ID canónico de rol e implicaciones de grupos, sin comparar números de
grupos entre bases. Conserva también definiciones de reglas de registro y
grupos de campos; su equivalencia funcional requiere pruebas con usuario normal.

El resultado separa captura válida de adopción: `adoption_ready=false`,
`reference_target_only=true`, `import_authorized=false` y
`record_rule_equivalence_certified=false` permanecen explícitos. Una coincidencia
numérica o de hash no concede permiso para sobrescribir un maestro.

## Resultados de G

- La fuente coincide con las filas y metadata selladas de C: **120 maestros,
  71 reglas y 91 XML IDs**. La M2M de entradas original permanece vacía; no se
  completa con demo. Se comprueban también sus hash y relaciones originales.
- **24 IDs originales ocupados**: tres estructuras, cinco tipos, diez reglas y
  seis categorías. G contiene cuatro estructuras, cinco tipos, cero entradas,
  49 reglas y 34 categorías. Se detectan **60 XML IDs de identidad diferente**;
  no son diferencias limitadas a noupdate. No se propone borrar o reutilizar G.
- **34 diferencias de metadata de campo**, incluidas 21 declaraciones ausentes,
  y **23 diferencias físicas de columnas**. De las 21 ausentes, 14 son físicas
  y siete no físicas. Además de los diez campos ya priorizados, faltan en el tipo
  de estructura `default_schedule_pay`, `default_work_entry_type_id`, `sequence`
  y `wage_type`: cada uno conserva cinco valores originales no NULL. No se
  descartan ni se sustituyen por defaults. Las siete ausencias no físicas
  necesitan contrato de API, no declaraciones vacías.
- La compañía no existe como propietario original de estructuras, reglas o
  categorías. El target tiene esos tres campos: adoptar originales debe dejar
  NULL explícito, sin el default de empresa actual. No se inventan propietarios.
- Una diferencia concreta de rol: usuario de Nómina nativo tiene CRUD sobre
  `hr.salary.rule`; oficial OCA solo lectura. Gerente e interno se compararon
  también. No se concede el rol gerente ni nuevos ACL para resolverlo. No hubo
  diferencias efectivas adicionales de grupos de campo en esta referencia.
- `input.type.name`: seis nombres escalares no traducibles en origen frente a
  almacenamiento traducible del destino. Falta política explícita para guardar
  el literal en el idioma base sin afirmar una traducción nueva. `rule.note`:
  71 NULL originales, con metadata translate distinta; conservar NULL físico no
  autoriza a ignorar esa diferencia o aplanar HTML traducido futuro.
- Diario por compañía: tres objetos JSON, una fila NULL y **12 slots**. Origen
  tiene cero incoherencias de compañía/diario; G tiene nueve slots sin extremo
  o dueño compatible. De cuatro compañías referidas, falta una y tres difieren
  en sus huellas/metadata. De cuatro diarios, faltan dos y otros dos difieren.
  Los tres slots numéricamente compatibles tampoco acreditan identidad adoptada.
  Cuentas débito/crédito y analítica conservan 71 NULL cada una; no se asignan
  cuentas para completar el plan ni se reactiva 210233.
- El **ID 462 está ocupado por `ir.actions.act_window`**, no por el reporte
  original. No se sobrescribe ni se deja la FK apuntando a esa acción. Falta
  identidad de acción/plantilla Community real y aceptación de impresión.
- Hay 71 enlaces escalares originales regla/estructura. La M2M de G contiene
  48 pares demo: solo tres coinciden numéricamente y eso no prueba identidad.

## Evidencia y reproducción

Raíz privada: `/opt/steps-validation/community-config-adoption-preflight-20261029/`.
En `evidence/`, informes definitivos `preflight-G-closure-before.json`,
`preflight-G-closure-after.json` y `tests-closure.log`, con permiso 0600 para los
JSON. Copia local fuera del checkout en
`C:/Users/tito4/.codex/local-artifacts/community-config-adoption-preflight-20261029/`.
No se copia la cápsula ni fórmulas al repo o al stdout.

```bash
sudo python3.10 tools/community/payroll_configuration_adoption_preflight.py \
  --capsule /opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json \
  --expected-capsule-sha256 14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140 \
  --target-database COMMUNITY_PAYROLL_API_CUSTODY_20261029G \
  --output /private/evidence/before.json
# Repetir con --baseline /private/evidence/before.json y otro --output.
python3.10 tools/community/payroll_configuration_adoption_preflight_test.py
```

Los 16 casos sintéticos pasan en Windows y Python 3.10: sellado, prohibición de
producción, secreto de fórmulas, IDs/XML IDs, tipos de columna, propiedad JSON,
traducciones/NULL, roles/grupos, referencias/report y comparación estricta entre
capturas. No son pruebas de un importador ni del motor salarial. Las dos lecturas
definitivas mantienen idénticas filas/metadata/referencias seleccionadas y
procedencia; no se hicieron DDL/DML, importaciones, upgrades o cambios de permisos.

## Siguiente puerta

Preparar Community oficial nueva sin demo, inventariar los maestros inevitables,
cerrar los campos/API, reporte, compañías/diarios/calendario/usuario de auditoría
y la identidad de todos los extremos. Resolver cada colisión antes de escribir,
sin borrar maestros ajenos, aplanar JSON, inventar traducciones o cambiar IDs.
Certificar roles, países y empresas mediante accesos normales antes de una
importación atómica autorizada. La preparación física en otra copia nativa no
equivale a conversión de metadata/ORM ni cierra estos bloqueos.

Continúan 71 reglas y contexto salarial completo, contabilización, Previred/libro,
históricos y productos restantes; una captura/importación parcial no acredita
conversión integral restaurable cero Enterprise ni resuelve el 31 de octubre.
