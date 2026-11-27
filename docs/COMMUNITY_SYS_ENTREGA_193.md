# SyS · Restauración de la entrega integrada de 193 módulos

El 27 de noviembre de 2026 se recuperó desde su propio respaldo la versión de SyS que reúne Nómina Chile, Finanzas, Biblioteca, Portal y el color de impresión. La instancia PostgreSQL 12.22 de la recuperación usó un directorio, rol de conexión y socket locales independientes de los del control. Odoo confirmó las versiones y rutas efectivas de los 193 proveedores LGPL/AGPL.

| Control previo al primer arranque | Resultado |
| --- | ---: |
| Filas de todas las tablas | 609.137 en 1.141 tablas |
| Secuencias con valor y estado exactos | 861 |
| Archivos físicos de la aplicación | 2.708 |
| Archivos del núcleo y de los proveedores | 22.261 |
| Esquema completo, incluidas vistas e índices | `a2535d3213a101a03297564d282b0aa2a2f6940f2fbc5073a2b707c3797b2e4d` |

## Resultados de los usuarios

Los nueve escenarios de nómina y finanzas reprodujeron los resultados de la versión .6.1. Incluyeron las cuentas y reglas originales, el ámbito por empresa, los días de trabajo, la validación, la contabilización, el lote y el Libro. Los 133 casos de las 12 empresas se cotejaron además individualmente con la aplicación nativa. Coincidieron 130 cálculos, sus 2.098 líneas y sus 130 confirmaciones contables. Las tres liquidaciones restantes devolvieron el mismo rechazo por revisión de contrato. En 97 casos el nuevo cálculo coincidió con la liquidación guardada. En 33 hubo la misma diferencia histórica en ambos motores. [Análisis de esos 33 casos](COMMUNITY_SYS_REGLAS_HISTORICAS.md)

Los dos operadores reprodujeron los 24 resultados de Previred y los 24 del Libro de Remuneraciones para las doce empresas. Se compararon archivos completos, columnas, filas, identidades y diagnósticos bajo los permisos originales. La muestra abarca 130 liquidaciones de octubre y tres de julio de 2026.

El gestor abrió dos PDF históricos distintos bajo los permisos originales. El PDF de Biblioteca mantuvo su vínculo con la nómina, el acceso por carpeta y la restricción de empresa. Un destinatario autenticado, otro usuario externo y un visitante reprodujeron las nueve respuestas HTTP anteriores al conceder y retirar el permiso. Las dos cuentas sintéticas recibieron contraseñas efímeras exclusivamente en la transacción revertida del ensayo. Se verificaron después las filas completas de usuarios y permisos.

Los dos operadores emitieron una representación local de una factura y una nota de crédito cada uno mediante la acción original. Texto, referencias, permisos, 141 tramos tipográficos y 140 trazados coincidieron con los originales. Las cuatro páginas coincidieron píxel a píxel en RGB a 96 y 144 ppp. [Comparación con el control previo al ajuste de color](COMMUNITY_SYS_COLOR_FISCAL.md)

Después de todas las pruebas, la fuente sellada siguió idéntica en todas sus filas, secuencias y 2.708 archivos. En la restauración se registraron 19 avances de secuencias por los ensayos. Los datos de negocio permanecieron idénticos. La primera impresión renovó una URL interna del CSS común al reextraer el módulo. De los 5.441 adjuntos, 5.440 conservaron sus filas completas y la nueva URL apunta a los mismos 476.850 bytes, SHA-1 `492528c576f5feb09cbf79c13b5bf847054fbb8e`. El almacén físico y todo el esquema permanecieron idénticos. [Ejecutor de los recorridos](../tools/community/exercise_sys_193.py)

## Custodia y recuperación

| Pieza privada | SHA-256 |
| --- | --- |
| Sello de 193 proveedores | `35dfde4c6734efcb9575d7957381d06d1874326d245605b11d7d84e4f08942da` |
| SQL reconstruido de 27.699.785 bytes | `06596b017042ac3d2ee43c61d7a1ae2f081805c1949f2c7d915c120628c83389` |
| Índice de transporte incremental | `38f4c970241ab4b82962b6581241ee5d6f5a639f732aa4feaf28940b3be350ae` |
| Comprobación final de datos y almacenamiento | `3c94f27c773964454b48f51c3e329c6afb30bbd56b013946635d92b635cd186e` |
| Comparación independiente de las cuatro páginas | `1426b8f44f29da25094e469cef43dc97518564dd4d1647a9ad4ba8b70a987cbb` |
| Archivo de aceptación, recibos y cuatro PDF | `4e039e9fcf464948f70d9247f89e5fd5bc47318eec824978cac86a42e1ea747a` |

El directorio privado `U46R/sealed` se conserva junto a su base firmada `U43C/fiscal-payroll-documents`, cuyo índice es `b033989da829ee87fa7233e3883f68cd1130eb52a4eb37ec8ebb8185e4d6c7e6`. Ambos directorios son necesarios. Se comprobó varias veces la reconstrucción íntegra del SQL a partir del original y de la diferencia comprimida. La entrega incremental requiere 3.493.200 bytes lógicos y reutiliza el código y los objetos sin cambios de FG. El archivo privado `U46R/operator-acceptance.tar.gz` contiene los cuatro PDF, los resultados y los manifiestos de los archivos públicos del sistema. Se verificó cada miembro tras guardar la copia local. La compresión transparente de su suplemento fiscal conservó los bytes originales y liberó más espacio que el consumido por el archivo de aceptación.

En Ubuntu WSL, desde `tools/community`, con `FG` y `KIT` apuntando a los directorios anteriores, se puede reconstruir el producto firmado y restaurarlo en la instancia en memoria.

```bash
set -e
python3 store_sys_193_release.py materialize "$FG" "$KIT" --recovery /dev/shm/sys-fg-193/sealed
python3 seal_local_sys_193.py restore "$FG"
python3 exercise_sys_193.py registry "$FG" "$REFERENCIAS"
```

El último comando usa los recibos privados de referencia de la estación. Para repetir la aceptación completa de esta entrega, las etapas siguientes de `exercise_sys_193.py` son `payroll`, `exports`, `documents`, `invoices` y `final`. La etapa de exportación necesita la clave original de cotejo sintético, que `forward_sys_export_comparison_key.py` transporta directamente a RAM. El control final adicional coteja la fuente privada U45P por lectura. Los archivos de verificación se guardan con `store_sys_193_release.py collect` y pueden comprobarse desde Windows con `compare_sys_fiscal_print_colors.py`. Las bases de producción permanecieron fuera del ensayo.
