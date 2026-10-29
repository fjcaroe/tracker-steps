# Fuente histórica Steps Transport localizada

Auditoría de solo lectura durante el bloque Community del 29-10-2026.
No se habilita ni se publica este módulo; no se crean modelos sustitutos.

La fuente `steps_transport` versión `1.5` existe en
`/opt/odoo18/custom_addons/steps_transport`, fuera del `addons_path` de Steps.
La ubicación ya figuraba en `ENTREGA_ORDENAMIENTO_AMBIENTES_2026-10-06.md`,
commit `38af2984`. La búsqueda en todas las referencias Git locales disponibles
no halló historia del directorio del módulo. La carpeta del servidor no pertenece
a un repositorio Git. No se copió su código al repositorio público ni se leyó
contenido de registros de negocio.

## Correspondencia con metadata conservada

La base Steps `karo_consultorias` conserva instalado `18.0.1.5`. Los dos modelos
declarados por la fuente son `steps.transport.route` y `steps.transport.route.line`.
Los 21 campos declarados coinciden por nombre con los de la base, que conserva
33 campos al incluir los automáticos; se inventariaron 41 XML IDs. Esto identifica
una candidata recuperable compatible por metadata, no certifica todavía cada
método, constraint, relación, secuencia o flujo contra la instalación histórica.

El manifiesto declara `base`, `hr` y `fleet`. Solo carga dos entradas de datos:
ACL y secuencia. Ambas ACL conceden CRUD a `base.group_user`; la base no tiene
reglas de registro para esos modelos. Hay 21 rutas HTTP/JSON: ocho `auth=public`
y trece `auth=user`. El conteo AST detecta 32 llamadas `sudo`, cinco `create`
y una `write`. Estos conteos son señales para una revisión concreta de cada
ruta; por sí solos no prueban una vulnerabilidad ni autorizan activar la API.

El manifiesto omite licencia, autor y sitio. Los valores `LGPL-3`/`Odoo S.A.` en
metadata instalada pueden proceder de defaults y no acreditan autoría/licencia.
La procedencia legal y la recuperación versionada de la fuente siguen como puerta
explícita. No se leyó ni copió código OEEL; tampoco se importó o ejecutó el addon.

## Evidencia y siguiente puerta

Evidencia privada local bajo
`C:/Users/tito4/.codex/local-artifacts/community-caf-core-20261029/`:
`transport-source-metadata.json`, `transport-native-schema.json` y el resultado
reproducible `transport-source-inventory.json`. Incluye hashes SHA256 de los ocho
archivos de fuente, campos, modelos, rutas y ACL; no incluye cuerpos de funciones,
credenciales, recorridos, personas ni datos de vehículos. La auditoría SQL usó
una transacción REPEATABLE READ READ ONLY y conservó los IDs existentes.

`tools/community/transport_source_inventory.py` reproduce la inspección estática
en la ruta explícita, sin importar módulos ni activar controladores. Exige salida
privada fuera del código y rechaza escaneo de cuerpos con licencia OEEL declarada.

Antes de habilitar una candidata: confirmar propietario y licencia; preservar
fuentes legítimas en su repositorio autorizado; comparar tipos/relaciones/IDs,
constraint y secuencia originales; auditar autorización, empresa y alcance de
cada ruta pública/sudo; probar roles, formularios y flujos en copia aislada de
Steps con el paquete exacto. No añadir toda la raíz antigua al `addons_path`.
La conversión de Steps conserva este frente pendiente aunque la fuente ya esté
localizada; no se silencia el diagnóstico con stubs o desinstalaciones.
