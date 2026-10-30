# T141 Recibo de recepción

## Entrega

Resuelto el 30-10-2026. Mensaje humano 9863 y adjunto 3446 revisados: capturas
de cabecera y operaciones, formas de texto y dos tablas EMF con pallets y
transporte. Los EMF se renderizaron a PNG con GDI. Nota interna 9867, etapa
Solved y ausencia de notificaciones/correos comprobada.

Mismo paquete publicado en Desarrollo, Cerro y QA-Cerro:

- Addon `step_packing_reception_report`, versión **18.0.1.0.1**.
- Commit certificado: `8e6e4556bd7e612520dbeaa3a4da9072f6637d1e`.
- Paquete `reception-report-v4.tar.gz`.
- SHA-256: `75298b75b5a839b5a4bb40e05567975d3cb30cadd214b94b79fda4d0c6da3656`.
- Árbol efectivo de Cerro y QA-Cerro, idéntico:
  `b0a8bae6558cc23e885fdcbf10f9ba56a0dcbde5dfb7793b847be4a0097a158a`.

La paridad acredita este módulo, no todos los addons ni prototipos. No usar
los paquetes preliminares; Desarrollo recibió la versión final antes de
publicar en los destinos del cliente.

## Comportamiento

Se adapta la acción nativa Recibo de entrega para recepciones entrantes de fruta
de Packing. Conserva logo, direcciones, permisos, firma, pie y acceso de impresión.
Los documentos de stock ajenos a ese alcance mantienen su formato e idioma.
No se crean campos, maestros, automatizaciones Studio ni registros paralelos.

Incluye guía, tipo y clase de fruta, lote (referencia de la recepción), operaciones
con pallets y envases físicos independientes de kilos, detalle de folios,
especie/variedad, cajas, bruto/tara/neto, promedio por caja, totales y transporte.
Los totales de operaciones separan las unidades de medida distintas. El promedio
es kilos netos / cajas totales; no una media simple de los promedios de las filas.

Los recibos se imprimen en español de Chile aunque el usuario o proveedor use
inglés, sin cambiar sus preferencias guardadas. Se conservan los valores reales:
no se rellenan datos opcionales vacíos ni se inventan números del ejemplo.
El formato se implementa en QWeb y helpers de lectura, sin validar recepciones,
modificar pesos, crear existencias o generar documentos reales al publicar.

## Pruebas y revisión visual

**27 pruebas aprobadas, nueve por copia fresca**, sobre el mismo paquete.
Cabecera/detalle en la acción nativa; pendientes y completadas; otros documentos
sin personalización; cajas y pesos del ejemplo; promedio ponderado y cero cajas;
unidades distintas; rechazo de otra empresa; pesos guardados conservados e
idioma español pese a un proveedor en inglés.

Se generaron **siete PDFs y se inspeccionaron sus trece páginas**: corto y largo
(63 tarjas) por destino, más el recibo real del adjunto en copia de QA-Cerro.
Todos pasaron control de texto dentro de página, presencia de las 60 filas
adicionales, encabezados repetidos, totales, transporte y revisión de imágenes.
Se ajustaron espaciado y líneas de tabla antes de certificar el paquete final.

El caso reportado conserva 600 cajas, 1.452,50 kg brutos, 252,00 de tara y
1.200,50 netos. Sus pesos y auditoría no cambiaron al renderizar. IDs y nombres
reales del caso se mantienen únicamente en el plan y PDF privados.

La publicación exige el manifiesto de revisión visual con SHA-256 de cada PDF
del mismo destino y copia certificada. No admite reutilizar una revisión de
otro paquete. Se comprobaron de nuevo versión, ruta efectiva, formulario,
menú de recepción y render de la acción nativa con usuarios existentes:
Desarrollo 2, Cerro/QA-Cerro 6. No se asignaron permisos nuevos. Servicios activos.

## Publicación y conservación

| Ambiente | Certificación | Respaldo en /opt/steps_backups/ |
|---|---|---|
| Desarrollo | t141d4, 9 pruebas | management_development_20261030T161005Z |
| Cerro | t141c4, 9 pruebas | management_cerro_20261030T161810Z |
| QA-Cerro | t141q4, 9 pruebas | management_qa-cerro_20261030T161935Z |

Huella exacta de los registros de negocio previos inventariados, antes/después
de instalar y de renderizar en copia. Mismo paquete, respaldo, bloqueo compartido,
rechazo de downgrade/concurrencia y overlays privados. QA-Cerro conserva sus
propios ejercicios; no se refrescó ni se promocionaron datos de capacitación.

Para los PDF de la copia privada de QA, el servidor de CSS/fuentes se liga solo
a 127.0.0.1. Una excepción temporal permite exclusivamente al UID de QA llegar
a ese puerto local y se retira en finally, bajo el bloqueo compartido. No se
permite otra dirección ni base. Se verificaron su retiro, el bloqueo de salida
y el rechazo de acceso a la base de producción al finalizar. El acceso HBA
exclusivo a la copia también fue retirado. No se cambiaron credenciales.

Evidencia privada: `/opt/steps-validation/t141-20261030/evidence/` y
`~/.codex/local-artifacts/t141-20261030/evidence/`. Incluye certificados, logs,
PDFs, revisiones visuales por hash, publicaciones, paridad y aislamiento.
Vista previa del caso real en `~/.codex/local-artifacts/t141-20261030/qa-cerro-v4/`.
