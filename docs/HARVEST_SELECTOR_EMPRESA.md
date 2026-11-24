# Selector de empresa en Harvest

Harvest 0.0.4 permite elegir **Empresa** en la misma pantalla de cosecha,
tanto en móvil como en escritorio. Recargar una vez Harvest después de la
publicación. La lista corresponde a las empresas autorizadas de la sesión
nativa; conservar las asignaciones y los permisos existentes.

Al cambiar, se verifica nuevamente la identidad y la empresa efectiva antes
de habilitar el registro. Jornadas, trabajadores, tarjas, configuración y
pendientes locales quedan separados por base, usuario y empresa. Al volver,
se recuperan los pendientes originales. Sin conexión o durante una
sincronización el selector queda bloqueado. Si falla la consulta, se restaura
la selección anterior y se verifica su contexto antes de habilitarla.

## Paquete y destinos

- Repositorio de la app: `stepconsulting/step_harvest`, rama canónica `main`.
- App: `258490f38336688d86c45b8053347804ab9a25d5`.
- Paquete web SHA-256: `db6e0ceb1e95d428492cde4cf660490aaf92b5783026a15095731b052fbad7f6`.
- JavaScript servido SHA-256: `71eb8e685e5fb008c9c1d19b0936f1d4ba66ee61094dade3b4f205f1b17323fb`.
- Backend conservado: `43b2c8e17023501375d018803891a8d453593eaa`.
- Destinos autorizados: Desarrollo, QA-Cerro y Cerro El Plomo.

Esta entrega cambia los archivos de Harvest, sin actualizar addons ni ejecutar
migraciones. `prepare_harvest_web_copy.py` comprueba que el backend de la copia
sea idéntico al destino, conserva un respaldo y compara los registros de
negocio. Cada copia debe pasar la prueba móvil de ida y vuelta con una entrega
pendiente. `verify_harvest_company_context.py` contrasta todas las empresas
autorizadas con la identidad y el contexto devueltos por el API real, sin
escribir datos de negocio.

`publish_harvest_web.py` exige la certificación y la prueba funcional de esa
copia, el mismo paquete ya publicado en Desarrollo, respaldo, bloqueo
compartido y ausencia de cambios concurrentes. Verificar también el selector
en cada ambiente publicado. Mantener los comprobantes, capturas y respaldos
en los directorios privados de la entrega, fuera del repositorio.

Pruebas de la app: 23 casos, incluidos permisos, identidad, errores de red,
restauración de la selección y conservación de pendientes. Compilación de
TypeScript y Vite verificada. La restricción de los prototipos SAG a Desarrollo
se conserva.
