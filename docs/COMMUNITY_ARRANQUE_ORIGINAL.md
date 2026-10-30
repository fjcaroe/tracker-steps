# Arranque privado sin semillas y almacenamiento de entradas — 29-10-2026

Bloque F aceptado desde la canónica `da1a1900`, incorporando los avances concurrentes
sin cambiar los 22 addons propios de [Inputs C / upgrade D](COMMUNITY_ENTRADAS_GUARDADAS.md).
Entrada Git congelada `56c76a9d234701ed2a1445bc0338b41dcecad53e`.
Se acepta un arranque de preparación sobre OCA real, sin adopción salarial original,
certificación financiera ni conversión integral. No habilita operación de nómina.

## Perfil de preparación

`build_original_bootstrap.py` deriva un perfil adicional desde los 52 archivos
AGPL fijados de Simple Digital y el builder normal intacto. Usa Community oficial
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`, con fuentes verificadas.
Los 22 addons propios de Inputs C permanecen sin cambios de código o dependencias.

El perfil contiene 49 archivos del proveedor. Omite exclusivamente:

- `data/hr_salary_rule.xml`: reglas y categorías de instalación.
- `data/hr_salary_structure.xml`: tipo y estructura chilena de instalación.
- `data/hr_employee_movement.xml`: ocho tipos de movimiento y 21 tipos de evento.

El tercer archivo requiere tratamiento explícito: el `create` AGPL de tipos de
movimiento busca «Nómina Chile» y genera reglas. Omitir sólo los dos XML salariales
no permite arrancar ni garantiza cero reglas. El perfil conserva ese método y
sus modelos reales; difiere su catálogo y la generación de reglas hasta adoptar
el conjunto original. No crea una estructura sustituta ni salta la validación.

También difiere exactamente el fragmento que asigna `unpaid_structure_ids` a
`work_entry_type_unpaid_cl` hacia la estructura omitida. Mantiene el tipo, el campo,
la relación y todo el resto de su XML. El fragmento y su hash quedan registrados.
**La política de ausencia sin pago y el catálogo de movimientos no están adoptados.**
Ambas puertas deben cerrarse antes de habilitar procesamiento chileno o movimientos.

Código Python, vistas, plantillas, ACL y demás archivos del proveedor mantienen
los bytes del derivado normal. El builder rechaza licencias no admitidas antes
de leer dependencias; fija versiones y fuentes limpias. Analiza definiciones y
referencias XML/CSV/Python, productores directos/transitivos de configuración y
rechaza huérfanas, referencias dinámicas sin contrato u omisiones adicionales.
La resolución externa se comprueba contra fuentes dependientes reales; la
colección offline la conserva como atestación de servidor, no como replay de
todos los cuerpos de dependencias.

El runner usa bases nuevas, overlays privados, bloqueo compartido y reservas
5/2 GiB. Fuerza `--without-demo=all`, comprueba cero módulos con demo habilitado
y exige 94 instalados/cero Enterprise. Los dos módulos estadounidenses de la
referencia normal (`l10n_us`, `l10n_us_account`) procedían de datos demo y quedan
fuera del arranque frío. Se mantienen los cuatro tipos oficiales de `hr_contract`;
su coincidencia numérica todavía no demuestra adopción de identidad original.

Las pruebas F ejecutaron los doce casos reales de entradas guardadas/lotes
sobre el motor OCA, además de formularios, acción web segura, menú, `default_get`,
permisos normales y rollback de actores. Se comprobó cero estructuras, reglas,
categorías, entradas, liquidaciones, contratos y catálogos diferidos antes y
después. La comprobación administrativa del enlace diferido se distingue del
actor normal: una compañía ajena a CL conserva su restricción de país.

## Almacenamiento de entradas: evidencia ya sellada

`audit_payroll_input_storage.py` leyó únicamente catálogos PostgreSQL y metadata
de modelos/campos/XML IDs en Inputs C Community, su copia nativa de Cerro y SyS.
Realizó dos capturas iguales por base, sin ORM, filas salariales, importes,
evaluación de reglas, DDL o DML. Las siete pruebas puras pasan en Windows y servidor.

| Contrato | Referencias nativa/SyS | Community Inputs C |
| --- | --- | --- |
| `amount` físico | NUMERIC sin límite de precisión/escala declarado, radix 10 | Float8, radix 2, 53 bits |
| NULL/default de importe | NULL permitido, sin default SQL | NULL permitido, sin default SQL |
| `code` | Relacionado no almacenado; columna ausente | VARCHAR NOT NULL almacenado |
| `contract_id` | Relacionado no almacenado; columna ausente | INT4 NOT NULL almacenado, FK RESTRICT |

La diferencia numérica representa un riesgo potencial ante una conversión;
**no se observó ni se afirma una pérdida de importes**. Los ejemplos Decimal son
matemáticos sintéticos y no cálculos de clientes. El plan no autoriza ALTER,
materialización, cambio de precisión ni conversión. Conservar los tipos y valores
históricos exige una política y prueba propias antes de cargar la API sobre datos.
Este hallazgo queda fuera de las siete brechas/cinco columnas de configuración;
no debe ocultarse contando sólo la matriz de maestros.

Evidencia privada: `community-original-bootstrap-20261029/input-storage`, con
seis capturas, código ejecutado y recibo. Plan SHA256
`c33c6f609c8abd6ce6011371ff276611e672d98f3a1493963834bb62106f152b`.
Recibo SHA256 `c0166a8ca56406105562a452f6ae9e39e6de2e4eddf083ed72398a59244abc04`.

## Diagnósticos conservados y aceptación F

A fue un build estático. B se detuvo antes de crear base por una suposición del
runner sobre el propietario PostgreSQL; ahora lo resuelve desde la configuración
registrada sin imprimir credenciales. C detectó el productor dinámico de reglas
del catálogo de movimientos. D instaló el perfil, pero su probe intentaba buscar
acciones con permisos administrativos y leer un tipo CL desde una compañía ajena;
se corrigió usando la API web oficial y separando la comprobación administrativa.
El diagnóstico focalizado de vistas/defaults/ACL pasó sin ampliar permisos.

E completó instalación e inspección, pero ejecutó cero pruebas porque el upgrade
del runner no marcaba API/Base. La guarda rechazó ese resultado. El runner ahora
incluye ambos módulos explícitamente. Los ensayos anteriores no son aceptación.
El diagnóstico focalizado ejecutó los doce casos y pasó sin fallos ni errores
tras esperar el bloqueo compartido de otra actualización. F repitió la pareja
en bases nuevas bajo el mismo bloqueo y superó la aceptación exacta:

| Entorno | Casos / omisiones | Módulos instalados / Enterprise | Alcance |
| --- | --- | --- | --- |
| Community oficial F | 12 / 0 | 94 / 0, cero demo | Arranque frío, formularios/defaults/menú/ACL y entradas/lotes reales OCA; rollback. |
| Copia fresca de Cerro F | 294 / 5 | 391 / 140 | Referencia nativa; no conversión. Omisiones de adaptadores exclusivos OCA documentadas. |

Ambos resultados tienen cero fallos/errores y la misma lista de 355 archivos de
addons; huella SHA256 `f2482a75e99846dd8dc65b9e327d10ac72973ff36f6f1b52a2bc3fc59360c010`.
Tar Git de entrada SHA256 `b6a2f8edbddf5c7b28d98ece96bef6fa0a3484c5f51a2496387a7cd9a7874266`.
Los 460 casos del perfil normal Inputs C siguen siendo una referencia distinta;
no se suman a los doce como una nueva suite fría de 472 casos.
Las 40 pruebas puras de builders, auditores y custodia también pasan.

La copia nativa preserva los valores de 921 tablas/proyecciones y 140 contadores
(1.061 contratos), históricos y 59.079 XML IDs originales con `noupdate`.
De los snapshots, 1.060 son literalmente iguales. La diferencia restante fue
verificada por un auditor nuevo, SQL readonly y reconstrucción tipada SELECT de
cinco filas/19 columnas del respaldo original: `base_weight` de un tipo de paquete
perdió únicamente ceros decimales finales en su representación, sin cambio numérico.
Los hashes
raw reconstruidos coinciden con antes/upgrade/después; el resto de campos, IDs,
NULL, texto y bytes permanece exacto. No se ejecutó DDL/COPY del dump, ORM,
conversión Float ni redondeo para demostrarlo. El verificador exige ese testigo
completo y rechaza cualquier otra diferencia; no se declara esa tabla idéntica
en representación. La primera igualdad dict del verificador era más estricta
que el contrato numérico versionado; su rechazo diagnóstico queda explicado.

El preflight frío confirma 120 maestros y 71 reglas originales intactos en la
fuente. Las colisiones de PK pasan de 24 a cuatro, exclusivamente en tipos de
estructura oficiales ya existentes; los conflictos XML IDs pasan de 60 a cero.
La procedencia nativa distingue 88 aliases originales y tres nuevos de referencia,
con sus PK distintas explícitas: no confunde los 91 con aliases originales.
La acción 462 sigue teniendo un conflicto de tipo con la referencia Community.
No se importaron maestros ni se ampliaron permisos.

La colección privada `community-original-bootstrap-20261029/acceptance-F` contiene
paquetes AGPL, logs, preflight, contratos, inventario, auditores y resultado
reproducible. El collector excluye dumps, filestore, credenciales y cuerpos OEEL.
El verificador offline usa exclusivamente código confiable del checkout; no
importa Python de artefactos ni accede a bases.

- Exportación inicial SHA256 `7c6a4dbe5f0f1704da700079cd4d65c1a84b6b8ee8accd8a0870b68acaad9eb4`.
- Testigo representacional SHA256 `5b816b6762ead0616b289368678f32deffbd80f0a9b2b746d8658e03a6744568`.
- Resumen offline SHA256 `c85d1b25e3e35787fb9f10d881a455ed09bfc4410bfe76097cb018fbe4ca24e7`.

La custodia final añade el testigo, inventario de cierre, revisión de omisiones,
pruebas puras y handoff; su manifiesto/recibo se conserva privado junto al tar
final en `/opt/steps-validation/community-original-bootstrap-20261029/`.
Los perfiles A–E siguen siendo diagnósticos, sin reutilizarlos como aceptación.

## Estado acumulado y siguiente bloque

Inventario fresco: Cerro 381/140/100, Steps 310/123/19 y SyS 332/142/17
(instalados/Enterprise/propios), sin cambios frente a Inputs C. Hay 126 módulos
propios, 30 fuera de Cerro y **54 apps instaladas con caminos Enterprise**.
Fuentes privadas incluidas; `steps_transport` conserva fuente recuperada e inactiva.

Siguen pendientes identidad/ACL y adopción de los 120 maestros/71 reglas,
referencias externas (compañías, calendarios, diarios y reporte 462), beneficios,
catálogos de movimiento y sus reglas. Se mantienen 27 contratos de configuración
cerrados, siete brechas, cinco diferencias físicas y los bloqueos de seguridad.
El arranque frío ya elimina los conflictos XML IDs y mide las cuatro colisiones
residuales. Faltan adoptar identidad y resolver `rule_ids`/tipo, beneficios,
requisitos de categorías/códigos/estructura y sus columnas. La comparación aún
mantiene tres observaciones de selección, una diferencia ACL y doce bloqueos de
seguridad. Ninguno queda resuelto por instalar sin semillas.
La auditoría de cierre volvió a observar el mismo inventario/hash de módulos y
fuentes que al inicio; no acredita que otros flujos productivos sean equivalentes.

Continúan certificación chilena con SyS, períodos/días, redondeo/YTD, asientos,
Previred/libro y consumidores; DTE/CAF/folios/firma/respuestas SII, Tesorería,
Calidad, Studio/Documentos/Firma y los demás productos. La conversión integral
restaurable con cero Enterprise sigue pendiente. **El 31 mantiene riesgo alto.**
Producción, QA-Cerro, vencimientos, pagadas/validadas y saldos no se modifican.
Calendar, Boolean bancario legado y 210233 continúan protegidos.

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro,
> operación, workflow, autonomía, continuidad y COMMUNITY_ARRANQUE_ORIGINAL.md.
> Conserva F aceptado (12 casos fríos/294 nativos), los 460 de Inputs C y el testigo
> representacional privado; A–E son diagnósticos. Antes de implementar revisa el
> inventario completo actualizado. Prioriza cerrar las siete brechas/cinco columnas
> y la frontera de identidad/ACL original: cuatro tipos ya existentes, 120 maestros,
> 71 reglas, beneficios y catálogos de movimientos/ausencias. Cierra referencias
> externas y acción 462; no sobrescribas colisiones ni infieras propietarios.
> Implementa un bloque de adopción real reversible, con respaldo y prueba exacta
> en Community oficial y copia fresca; distingue referencia de conversión.
> Conserva NUMERIC, NULL y relaciones originales; no permitas cast automático a
> Float8 ni asignes propietarios/valores inferidos. Certifica procesos reales SyS
> sin recalcular pagadas y mantén DTE/SII y conversión integral visibles. Respeta
> todas las restricciones; commits/push, integra sólo lo validado y verifica handoff.
