# Arranque privado sin semillas y almacenamiento de entradas — 29-10-2026

Base canónica `da1a1900`. Se conserva [Inputs C / upgrade D](COMMUNITY_ENTRADAS_GUARDADAS.md).
La aceptación del perfil frío está pendiente; este documento registra implementación
y diagnósticos para retomarlos sin repetir lo ya comprobado. No acredita conversión.

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

Las pruebas previstas ejecutan los doce casos reales de entradas guardadas/lotes
sobre el motor OCA, además de formularios, acción web segura, menú, `default_get`,
permisos normales y rollback de actores. Se exige cero estructuras, reglas,
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

## Diagnósticos y cierre pendiente

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
tras esperar el bloqueo compartido de otra actualización. Se prepara F en una
base nueva; faltan su aceptación exacta, referencia nativa fresca, preflight y
verificador offline. Los diagnósticos no sustituyen esa aceptación.

## Estado acumulado y siguiente bloque

Inventario fresco: Cerro 381/140/100, Steps 310/123/19 y SyS 332/142/17
(instalados/Enterprise/propios), sin cambios frente a Inputs C. Hay 126 módulos
propios, 30 fuera de Cerro y **54 apps instaladas con caminos Enterprise**.
Fuentes privadas incluidas; `steps_transport` conserva fuente recuperada e inactiva.

Siguen pendientes identidad/ACL y adopción de los 120 maestros/71 reglas,
referencias externas (compañías, calendarios, diarios y reporte 462), beneficios,
catálogos de movimiento y sus reglas. Se mantienen 27 contratos de configuración
cerrados, siete brechas, cinco diferencias físicas y los bloqueos de seguridad.
La instalación fría está preparada para medir colisiones residuales, no para
declarar esos maestros adoptados o nóminas operacionales.

Continúan certificación chilena con SyS, períodos/días, redondeo/YTD, asientos,
Previred/libro y consumidores; DTE/CAF/folios/firma/respuestas SII, Tesorería,
Calidad, Studio/Documentos/Firma y los demás productos. La conversión integral
restaurable con cero Enterprise sigue pendiente. **El 31 mantiene riesgo alto.**
Producción, QA-Cerro, vencimientos, pagadas/validadas y saldos no se modifican.
Calendar, Boolean bancario legado y 210233 continúan protegidos.

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro,
> operación, workflow, autonomía, continuidad y esta aceptación. Recupera el bloque
> frío pendiente antes de repetir pruebas verdes: perfiles A–E son diagnósticos.
> Cierra la pareja exacta, preflight, evidencia y handoff. Después prioriza identidad
> original sin sobrescribir colisiones: cuatro tipos inevitables, 120 maestros,
> 71 reglas y catálogo de movimientos/ausencias con referencias y ACL completas.
> Conserva NUMERIC, NULL y relaciones originales; no permitas cast automático a
> Float8 ni asignes propietarios/valores inferidos. Certifica procesos reales SyS
> sin recalcular pagadas y mantén DTE/SII y conversión integral visibles. Respeta
> todas las restricciones; commits/push, integra sólo lo validado y verifica handoff.
