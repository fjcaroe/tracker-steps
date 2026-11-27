# Exportaciones de nómina de SyS por empresa y operador

La referencia U40N conserva el proveedor nativo. La instalación Community U40I
se verificó en procesos Odoo sin salida de red. Se tomó el último mes con
liquidaciones cerradas por empresa, con ambos operadores internos existentes y
su única empresa activa en cada solicitud. Cada operador contaba con el permiso
de generación y el rol de nómina de su empresa. La liquidación y sus líneas se
verificaron con el mismo usuario antes de delegar a los proveedores.

El censo incluye 130 cierres en once empresas de octubre de 2026 y tres en una
empresa de julio. Otra empresa sólo tiene liquidaciones en verificación. La
consulta de cierres la excluye. Se usó el informe consolidado mensual, incluidos
los empleados sin departamento. Los módulos compartidos registraron las mismas
versiones en los dos motores, con Simple Digital 18.0.1.0.0, Previred 18.0.3.8.7
y su integración Simple Digital 18.0.2.4.1.

El Libro de Remuneraciones produjo 133 filas de 147 columnas por operador,
sin omisiones ni identidades adicionales. Las 24 comparaciones por empresa
y operador coincidieron tanto con cabecera como sin ella. El proveedor
nativo de Previred generó 133 principales y 69 anexas, de 105 columnas.
Aplicó la especificación 84 en julio y la 98 en octubre. Hubo 19 avisos en
siete empresas y ninguna denegación de generación.

En U40I coincidieron los archivos de Previred de 11 empresas y los diagnósticos
completos de las 12. Para ambos operadores de la empresa restante aparecieron
seis diferencias de tipo de jornada en el campo 93, cinco principales y una
anexa. El calendario conserva 24 horas semanales y 40 horas de referencia. La
columna original y sus 41 calendarios existían íntegros, pero el registro activo
de Community no exponía `resource.calendar.hours_per_week`. El extractor común,
idéntico en ambos motores, usaba en consecuencia sólo la referencia de 40 horas.
El recibo privado de la comparación U40I tiene SHA-256
`4f7bf3d98e7b05eab9046a96ad50baf8e52a474a588f931f3fbf31bdbb1e29c9`.

## Repetición sobre la instalación J

En U41X3 se cargó el proveedor SyS 18.0.1.5.1 desde un directorio privado
sobre la instalación J. El ejecutor comprobó el alta del campo en el registro
activo, el valor semanal original y sus dependencias. El proveedor lee la misma
columna de `resource_calendar`. Con nuevos horarios de prueba se cotejaron las
jornadas regulares y bisemanales, modificaciones de tramos, tramos con fecha,
licencias, recursos individuales, secciones y horarios flexibles. Se observaron
los mismos resultados en el proveedor nativo y en Community. Los ensayos con
horarios de prueba se ejecutaron en memoria dentro de transacciones de sólo
lectura.

| Cotejo contra el proveedor nativo | Resultado U41X3 |
| --- | --- |
| Empresas y cuentas autorizadas | 12 empresas, 2 operadores cada una |
| TXT Previred | 24 de 24 archivos idénticos byte por byte |
| Filas por operador en las 12 empresas | 133 principales y 69 anexas de 105 campos |
| Diagnóstico de Previred | 19 avisos en 7 empresas, 0 errores y coincidencia de mensajes y pantallas de validación y generación |
| Libro con cabecera y sin ella | 24 de 24 comparaciones idénticas en cada modalidad |
| Libro por operador | 133 filas de 147 columnas, 133 identidades cotejadas |
| Jornadas, contratos y liquidaciones | 41 calendarios y 512 tramos originales, con sus huellas conservadas |
| Generación y alcance | Los dos operadores generaron ambas salidas en todas las empresas; los registros de ensayo del asistente se revirtieron |

El paquete del proveedor tiene SHA-256
`0c9f3cfb38ac5e6d13c61a6af77c637db8d90104e073c9948b6c4ed624b65026`.
Los recibos contienen huellas de archivo completo, de filas y de cada columna.
Los mensajes e identidades se compararon mediante HMAC con una clave privada
compartida por los dos ensayos. La comparación integral tiene SHA-256
`1b7d91c189eca56845d4a430fc2db4ab007a8c46e6dca1deecdf20e53a104328`.
La instalación persistente del proveedor queda para la siguiente integración.
