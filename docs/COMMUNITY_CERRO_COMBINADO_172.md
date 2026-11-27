# Cerro Community con 172 módulos

La copia fría U42H se restauró desde la biblioteca de Cerro U41L. Las 23
vistas activas de Studio tenían las mismas filas que la restauración nativa
de custodia U40Q. Tras adoptar el campo de empresa de la lista de materiales
se instaló primero `step_cerro_studio_adoption`, luego el conjunto de
propietarios. La actualización posterior volvió a cargar estos mismos
módulos. En cada fase los 23 registros completos fueron idénticos a U40Q.
Esto incluye las arquitecturas actual y anterior, origen, propietario,
auditoría, prioridad y permisos. La huella conjunta de esas filas fue
`a0e0ae80a5c095ae1ca7beb27ea16e1d3670ccba563309dc5287f4e0a34c2431`.

Las 172 aplicaciones instaladas tenían licencia libre. Se conservaron las 23
guardas y 62.030 identificadores externos sin cambios. El usuario de
inventario recorrió el menú y la acción nativos de 17 vistas. En 14 leyó los
mismos campos de Studio sobre el registro original. En diez coincidió la
fila completa del cliente web. Se conservaron los 53 fundos, los alcances
por empresa y productores, las 14 estimaciones, sus 11 cuarteles y las
cuatro relaciones originales de categoría. El ensayo previo con el mismo
conjunto en U42B incluyó la creación, copia y modificación de una lista de
materiales y la denegación de escritura al usuario público. Las siete listas
guardadas mantuvieron sus dos empresas.

## Paquete reproducible

Las 24 fuentes del paquete son las que cargó U42H para este conjunto. Las
otras dependencias y la biblioteca proceden del entorno Community
restaurado. Se compararon los 410 archivos y se reprodujo el archivo tar
byte por byte desde este árbol Git. En un directorio de salida privado
se puede regenerar con:

```console
python tools/community/build_cerro_verified_172.py --source . --output /ruta/privada/cerro-combinado-172.tar
```

SHA-256 del archivo para instalar:
`58d0cff8c32074c183b73ff5b317c434cc9141d291f6252ba41a331b95838b95`.
El recibo de fuentes está en `tools/community/cerro_studio_172_receipt.json`.
El acta de instalación fría y actualización se conserva en
`U42H/qualified-combined.json`, SHA-256
`adddcf0dde7d30462b88e2caa85bae622253a8298d32c780234c607b7d8d7656`.
El acta de BoM, Packing y Fundos de U42B se conserva en
`U42B/combined-packing-verified.json`, SHA-256
`b45c1483a169adf2fd58f9dd729c57f0597bd89da941163cdf7f18d76e146f00`.

Los alcances adicionales de Presupuestos, Fletes, control de calidad,
guías fiscales y de la actualización del sistema nativo completo se
siguen ensayando por separado.
