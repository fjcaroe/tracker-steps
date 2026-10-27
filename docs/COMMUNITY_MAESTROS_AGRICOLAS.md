# Maestros agrícolas Community

Extrae las definiciones propias de Steps desde `step_hr`; no implementa ni
incluye código Enterprise. Dependencias nativas: Contabilidad, Flota y
Direcciones extendidas. Conserva 18 modelos, las extensiones de producto y
cuenta analítica, sus tablas, relaciones, vistas y permisos.

Los namespaces `step_hr` y `step_agriculture_core` apuntan a los mismos
registros. El preinit adopta los XML IDs existentes y rechaza conflictos;
el postinit mantiene la API antigua en instalaciones nuevas. También protege
los campos heredados y selecciones generados por Odoo. La adopción no copia
datos de negocio ni cambia sus IDs.

Los campos agrícolas de productos y cuentas analíticas conservan la
nulabilidad efectiva de Cerro. Los productos generales y cuentas ajenas a la
agricultura siguen siendo válidos. El formulario agrícola solicita sus datos
y el grupo de labor se exige cuando el producto es una labor; no se rellenan
valores inventados en registros existentes.
Las empresas de los cuatro catálogos también admiten el alcance compartido
durante toda la carga intermedia, antes de que se cargue la extensión de
catálogos: no se asigna la empresa por defecto a registros compartidos.

`step_agriculture_catalogs` mantiene exactamente sus relaciones multicompañía,
reglas y contratos de compatibilidad. Packing, Tarjas de Fruta y el puente
agrícola de Gestión y Costos consumen este núcleo sin Nómina ni Gantt.
Los menús anteriores de Actividades conservan su identidad, ubicación y
restricciones. En destinos con esos menús, el nuevo acceso independiente queda
inactivo para no crear atajos alrededor de sus grupos. Una instalación pura
Community usa el acceso independiente «Maestros agrícolas».

## Actualización de una base existente

Probar primero el paquete completo en una copia fresca del destino:

```text
-i step_agriculture_core
-u step_hr,step_agriculture_catalogs,step_packing,step_inventory_fruit_tag,step_management_costs,step_management_costs_agriculture
```

Usar `tools/community/validate_agriculture_core.py`, con bloqueo compartido,
filestore privado y la configuración explícita del destino. No ejecutar esos
argumentos directamente sobre producción. La premigración del puente de
costos adopta también los enlaces existentes entre acción y vistas, evitando
el borrado y recreación del comando XML anterior.
El ejecutor privado `tools/ops/run_agriculture_upgrade.py` conserva además
las FKs canónicas, el orden previo de los menús y los enlaces de acción/vistas
cuando el XML intenta recrear exactamente la misma configuración. Un grafo
diferente sigue el tratamiento normal y debe superar la comparación de IDs.
No instala estos adaptadores en procesos de servicio ni cambia sus fuentes.

La comprobación histórica conserva mensajes, seguimiento, seguidores y
adjuntos. Solo normaliza los timestamps de escritura de iconos binarios de
menú que Odoo vuelve a cargar: conserva sus IDs, contenido y demás metadatos.
Las nuevas membresías del menú del núcleo se controlan por separado de las
membresías originales, que deben permanecer exactas.

Esta entrega permite instalar esos consumidores en Community. No permite
desinstalar todavía `step_hr`, Nómina, DTE, Calidad, Studio o Enterprise de
una base completa: quedan consumidores y funciones que deben migrarse antes.
