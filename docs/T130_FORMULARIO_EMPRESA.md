# T130: formulario completo de Ajustes / Empresas

Solicitud y adjunto 3423 revisados el 28-10-2026. Entrega autorizada en
Desarrollo, Cerro y QA-Cerro. T129 ya estaba resuelto por un humano y no se modifica.

## Causa y solución

Odoo elige vistas primarias por prioridad, nombre e ID. Los formularios reducidos
`company.export.folios` y `company.packing.stock.configuration` compartían la
prioridad 16 con `res.company.form` y quedaban antes por nombre. Sus listados
también podían sustituir el listado general.

`step_company_form_restore` da prioridad 5 a las dos vistas estándar y vincula
la acción nativa al listado estándar. Reutiliza la identidad, permisos, dominios
y todas las extensiones del formulario nativo; no reconstruye una empresa ni
copia sus campos a otra tabla. Folios y Bodega Packing mantienen sus enlaces
explícitos y sus formularios reducidos.

Se detectó además en Desarrollo un layout Previred de Studio que referenciaba
cinco campos inexistentes. Su migración versionada exige reconocer exactamente
ese conjunto y encontrar los cinco parámetros canónicos nativos. Conserva el
ID y la arquitectura originales como vista inactiva y adopta su identidad externa
para protegerla de la retirada futura de Studio. No recrea campos Studio ni
calcula tasas por suposición.

`step_company_form_restore_payroll` agrega la pestaña Previred en código y usa
`caja_compensacion`, `has_mutual`, `mutual`, `rate_base` y `rate_additional` del
proveedor oficial instalado. Comparte esos campos con Instituciones Relacionadas,
sin campos paralelos ni modificaciones de valores o cálculos.

## Alcance de las pruebas

Las pruebas comprueban selección predeterminada del formulario y listado, todas
las extensiones nativas, resistencia a otra vista primaria de igual prioridad,
accesos explícitos a Folios/Packing, carga de los datos reales y edición en el
búfer del formulario, sin guardarlos. El caso de uso de T130 es recuperar la
pantalla y visualizar información; no completar la configuración fiscal.
También se verifica la pestaña Previred nativa y la ausencia de referencias a
los cinco campos obsoletos.

El flujo de usuario usa perfiles existentes, menú real, listado y formulario
completos; conserva la empresa, su identidad, moneda y datos. La prueba no evita
validaciones nativas ni introduce datos fiscales ficticios en ambientes activos.

## Configuración DTE diferida, autorizada por el usuario

El usuario respondió que no dispone del correo DTE y pidió permitir guardar la
empresa dejando señalado que ese dato se requiere para el proceso con SII.
`step_company_edi_readiness` retira únicamente la obligatoriedad en el formulario
de los cinco datos DTE, y muestra un aviso calculado con lo que falta. No guarda
marcadores ficticios ni cambia los valores existentes. Las pantallas generales
de configuración nativas ya permitían esos campos vacíos.

El flujo de documentos mantiene la llamada a `_l10n_cl_edi_post_validation` del
proveedor instalado, incluidas sus validaciones de correo, actividades, oficina
y excepciones por tipo de documento. Después comprueba que número y fecha de
resolución estén informados para SII/SIITEST, antes de crear el XML. Los documentos
manuales que no usan ese flujo y el modo de demostración conservan su comportamiento.

Las pruebas verifican guardar datos generales con correo/resolución vacíos,
el aviso, el rechazo nativo por correo DTE y el control de resolución. Los casos
de validación usan documentos nuevos en memoria; no emiten ni envían documentos.
Los datos fiscales de los ambientes activos permanecen intactos.

Referencia técnica: [instructivo de emisión SII](https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf).

Publicar el mismo paquete comprobado en copias frescas, con respaldo y bloqueo,
sin refrescar QA-Cerro ni alterar su aislamiento. Las evidencias se guardan fuera
del repositorio público.

## Entrega completada el 28-10-2026

T130 quedó Solved con nota interna 9778 y comprobación de cero correos o
notificaciones. T129 ya estaba Solved y no se modificó. No hay tickets nuevos
posteriores al 130 en la consulta final de esta entrega.

Paquete: `1b066c9243085ef6138893cb8b0b700592564972`.
SHA-256: `f4d274378755f55d3fe0f6e7f0811f0a355fbbbca615468ee17da6dae8b2067e`.
Versiones 18.0.1.0.0 de `step_company_form_restore`,
`step_company_form_restore_payroll` y `step_company_edi_readiness`.

| Destino | Copia fresca aprobada | Respaldo de la publicación final |
| --- | --- | --- |
| Desarrollo | MANAGEMENT_QA_DEVELOPMENT_t130d5 | management_development_20261028T204350Z |
| Cerro | MANAGEMENT_QA_CERRO_t130c5 | management_cerro_20261028T204529Z |
| QA-Cerro | MANAGEMENT_QA_QA-CERRO_t130q5 | management_qa-cerro_20261028T204729Z |

Once pruebas por copia: **33 ejecuciones aprobadas**. Se verificaron después
de publicar versión y fuente efectivas, menú, listado, formulario completo,
pestañas heredadas y Previred, aviso DTE y ausencia de obligatoriedad fiscal
en el guardado general. Folios y Bodega Packing conservaron sus accesos explícitos.
Los perfiles existentes se usaron sin elevar permisos. Las huellas de datos
originales se conservaron, sin alterar contactos, empresas, monedas, instituciones,
tasas, resolución SII ni correo DTE. No se generaron documentos reales de prueba.

QA-Cerro conserva sus datos de capacitación, bloqueo de salida y denegación de
acceso a producción. El paquete idéntico se publicó con respaldo, bloqueo y
validación de concurrencia, mediante overlays privados. Todos los cambios útiles
se integraron a la rama canónica del producto.

Evidencias privadas: `/opt/steps-validation/t130-20261028/evidence/` y
`~/.codex/local-artifacts/tickets-20261028-new/evidence/`. Respaldos completos
bajo `/opt/steps_backups/` con permisos privados.
