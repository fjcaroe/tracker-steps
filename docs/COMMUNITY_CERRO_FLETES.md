# Cerro El Plomo · directorio de Fletes

El perfil de 186 módulos libres reúne Fletes, Presupuestos, las listas de materiales y Packing. El usuario 6 alcanzó 20 de las 23 rutas originales. En 18 pantallas obtuvo el mismo registro y los mismos valores de Studio que en el sistema nativo. En 15 coincidió la lectura completa del cliente web.

El directorio conserva los siete tipos de despacho, las 14 vinculaciones a empresas y las dos guías históricas. La acción 1367 abre la lista original desde los menús 979 y 1177. Las ocho empresas autorizadas 1, 2, 3, 4, 29, 30, 31 y 41 mostraron respectivamente 2, 6, 2, 2, 5, 5, 6 y 2 tipos. El sistema rechazó separar del tipo de despacho una empresa presente en una guía.

En la instalación fría U43Z, la versión 18.0.2.7.6 se instaló y volvió a actualizar. El registro quedó con cero módulos Enterprise, cero licencias no libres y cero transiciones pendientes. La regla 645 y el permiso 2014 conservaron todas sus columnas, incluidas las fechas de auditoría. Las 23 filas históricas de Studio, las 62.030 identidades protegidas, las estimaciones y las relaciones de categorías siguieron coincidiendo con el origen. El recibo privado `U43Z/qualified-freight.json` tiene SHA-256 `35b558e377cda2964365b720d9e8a25386d6d30d9a90b724cf99f996b191034b`.

## Fuentes y datos del directorio

La entrega utiliza la aplicación completa de Fletes y sus dependencias de flota, maquinaria, movilización y agricultura. Los campos del destinatario y de empresas del despacho proceden de los proveedores nativos de Packing. La protección de las guías consulta su relación histórica cuando el módulo fiscal completo queda fuera de la cohorte.

Se reconstruye el archivo con `tools/community/build_cerro_verified_172.py --profile freight --source <repositorio> --output <archivo-nuevo>`. La versión 18.0.2.7.6 contiene 43 archivos. Su SHA-256 es `769a584e2bf3e1c7009f6ce2fd5fbd00d68228ac900c2d066582b69ea3d62c43`. El ensayo previo de U42P con la versión 18.0.2.7.5 pasó el circuito funcional y actualizó la fecha de escritura del permiso 2014. El recibo privado de esa etapa es `U42P/qualified-freight.json`, SHA-256 `1c4684bd513f456c7fbe9a3ed61e2ace8b474acc0ed58e39cd5ed3d394b4ee89`.

## Pantallas pendientes de lectura completa en el perfil de 186

| Vista | Ruta original | Primer dato que requiere otro proveedor |
| --- | --- | --- |
| 4845 | Pendiente | Conceptos de pago de exportación |
| 5189 y 5194 | Pendientes | Modelo de producción de Packing |
| 5192 | Sí | Datos del receptor de exportación |
| 5193 | Sí | Estado de la tarja de Packing |
| 5187 y 5244 | Sí | Controles de calidad del traslado |
| 5245 | Sí | Archivo fiscal chileno del traslado |
