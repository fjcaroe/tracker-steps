# Cerro El Plomo · Presupuestos en Community

La restauración U43Z instaló y actualizó los presupuestos de Cerro desde la copia privada de noviembre. La lista de materiales, los maestros agrícolas, Packing y los presupuestos convivieron en el mismo registro de 185 módulos. El censo registró cero licencias no libres y cero transiciones pendientes.

El usuario 6 alcanzó 19 de las 23 rutas originales. En 17 pantallas coincidieron el registro y los campos de Studio con el control nativo. En 14 coincidió la fila completa del cliente web. El corte anterior, de 172 módulos, daba 17 rutas, 14 lecturas de Studio y diez filas completas. U42E ensayó antes la extensión presupuestaria con 184 módulos. U43Z incorpora además la lista de materiales.

La restauración partió de U41L. El motor instaló primero la adopción de Studio, luego los proveedores del perfil de 172 módulos y, por último, la extensión de Presupuestos. Volvió a actualizar los proveedores y comprobó las filas originales después de cada fase.

- Se conservaron las 23 filas completas de Studio, con SHA-256 conjunto `a0e0ae80a5c095ae1ca7beb27ea16e1d3670ccba563309dc5287f4e0a34c2431`. Esto incluye los seis historiales de arquitectura afectados por los primeros ensayos.
- Se conservaron los 62.030 identificadores externos protegidos y las 23 guardas. Las 14 estimaciones, las cuatro relaciones de categoría de fruta y las vinculaciones 836/837 de la acción histórica coincidieron con el origen.
- Cosecha y el proveedor de personal comparten 29 nombres históricos de tres asistentes de Nómina. Al cargar Cosecha se cotejan modelo e identidad con los mismos nombres del proveedor original. Las 29 parejas conservaron todas sus columnas, incluidas las marcas de actualización y auditoría.

El recibo de la instalación y actualización desde cero es `U43Z/qualified-archive.json`, SHA-256 `be6a510cf41f5b02baf4fc57b248affc216187a3f23c29af48e4905aeb1634fb`. El primer cotejo del candidato integrado está en `U42P/qualified-archive.json`, SHA-256 `83cf709fc1201c76ca447fd146671e959224b71d99934a569459e04bc18d5ac4`.

## Reproducción

`tools/community/build_cerro_verified_172.py` comprueba los archivos del repositorio antes de reconstruir los paquetes. El argumento `--source` recibe la raíz del repositorio y `--output` una ruta nueva. La prueba de restauración se ejecuta con `tools/community/check_cerro_combined_budget.py --fresh`.

| Perfil | Módulos de la entrega | Archivos | SHA-256 |
| --- | ---: | ---: | --- |
| `--profile 172` | 24 | 410 | `58d0cff8c32074c183b73ff5b317c434cc9141d291f6252ba41a331b95838b95` |
| `--profile budget` | 13 | 325 | `b31ed47840f07a38318e80473a76b02038a4b68d4a59d30e3ad446320bfe6885` |
