# T127 — campos de la hoja BPA de productos

Solicitud revisada el 27-10-2026: cuatro tickets abiertos, T124 a T127.
T127 pide equiparar la hoja BPA de `product.template` de Cerro y QA-Cerro
con Desarrollo. Se leyeron descripción, comentarios y adjunto 3418 con sus
tres capturas. No pide asignar valores o clasificaciones a productos.

## Inventario comprobado sin escrituras

Los campos nativos de carencia mayor, UE, USA y máximo de aplicaciones ya
existen en los tres destinos, junto con `agriculture_active_ingredient_id`.
El formulario nativo incorpora las cuatro carencias/cantidades; hay que verificar
la ubicación de sustancia activa en la composición efectiva de la hoja BPA.

En Desarrollo quedan siete campos manuales de registro:

| Campo heredado | Tipo | Destino propuesto en código |
| --- | --- | --- |
| x_studio_concentracin | Texto | registration_concentration |
| x_studio_formulacin | Texto | registration_formulation |
| x_studio_cdigo_formulacin | Texto | registration_formulation_code |
| x_studio_aptitud_plaguicida | Relación | registration_aptitude_id |
| x_studio_titular_autorizacin | Texto | registration_authorization_holder |
| x_studio_primera_autorizacin | Fecha | registration_first_authorized_on |
| x_studio_vencimiento_autorizacin | Fecha | registration_authorization_expires_on |

La relación apunta al maestro Studio `x_aptitud_plaguicidas`, con **63 registros**
en Desarrollo. Sus campos propios son nombre obligatorio, activo, código,
observación HTML y secuencia. Cuenta con historial y actividades; no se debe
convertir la relación en texto ni generar un maestro paralelo. En Cerro y
QA-Cerro ese maestro/los siete campos manuales no existen.

`tools/ops/audit_product_bpa.py` guardó campos, IDs, tipos, referencias, XMLIDs,
vistas, accesos y las 63 filas históricas en artefactos privados. Probado por
lectura en los tres destinos. No selecciona secretos ni modifica datos.

## Ejecución pendiente

1. Crear un addon de registro BPA que use la sustancia activa nativa existente.
2. Migrar el maestro manual a un modelo nativo, por ejemplo
   `step.agriculture.pesticide.aptitude`, renombrando tabla, campos, referencias
   y metadatos en el sitio, conservando IDs, datos, mensajes y accesos.
   Migrar las siete columnas/identidades de producto y sus vistas, reglas y
   demás referencias; no ampliar Studio. Usar el patrón comprobado de
   `step_agriculture_records/migrate_schema.py`, con contrato específico propio.
3. En destinos que no tienen esos campos, instalar el mismo esquema nativo.
   No copiar automáticamente productos o clasificaciones desde Desarrollo.
4. Probar la conversión en copia fresca de Desarrollo, y la instalación en
   copias frescas de Cerro y QA-Cerro. Exigir conservación de los 63 registros,
   todas las relaciones/fechas/textos y auditoría; probar formulario y selección
   con usuario existente, sin elevar permisos.
5. Publicar el mismo paquete primero en Desarrollo y luego en los dos destinos,
   con respaldos, exclusión, guardas concurrentes y comprobación funcional.

T127 sigue **sin cambios publicados**; no hay código funcional nuevo de BPA
ni migración ejecutada. No cerrar por este inventario.

Artefactos: `/opt/steps-validation/t127-inventory-20261027/{development,cerro,qa-cerro}.json`
y carpeta privada local
`C:/Users/tito4/.codex/local-artifacts/helpdesk-20261027-four-tickets/`.
