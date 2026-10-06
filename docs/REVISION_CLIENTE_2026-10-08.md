# Prueba del jueves — aplicaciones y ambientes

La definición del cliente del 06-10-2026 reemplaza los destinos de documentos
anteriores. **Toda revisión funcional se hace en Desarrollo**:
https://desarrollo.stepsapp.cl. Demo-SYS se reserva para Nómina Simple Digital
y soporte de Luis. Producciones: SyS, Steps / Karo y Cerro El Plomo.

## Recorrido mínimo de aceptación

| Área | Entrada en Desarrollo | Caso que debe revisar el responsable |
|---|---|---|
| Nómina | Nómina / Empleados / Contratos | Parámetros de Simple Digital, días de contrato y atrasos; comparar una liquidación nueva de prueba. No recalcular una pagada. |
| Actividades y App | Actividades y `/task/` | Maestros del ERP, cuadrilla, OT, cantidad/horas, envío y recepción en consola. Comprobar reintento sin duplicar. |
| Cosecha y App | Cosecha y `/cosecha/` | Fundo, especie, variedad y centro existentes; registro, kilos/envases, envío y recepción. Verificar saldo y propietario. |
| Gestión y Costos | Gestión y Costos | Presupuesto → plan → OP; estimación con temporada/especie/variedad seleccionadas; costo real y comparación por centro analítico. |
| Contabilidad | Contabilidad | Consultar asiento, mayor y saldo con filtros de empresa/fecha. Comparar con los documentos de origen. |
| Packing | Packing | Recepción C → OP/OT → materiales → cuadratura/cierre → costeo. Revisar capitalización explícita antes de aprobarla. |
| Productores | Productores | Contrato, precio por clasificación, documentos anteriores, liquidación y consolidado por temporada/especie. Evitar duplicar la factura. |
| Exportaciones | Exportaciones | Programa, embarque, gastos exteriores, IVV revisado/provisión y nota definitiva con reversión exacta. |

Las aplicaciones de labores y cosecha son las PWA Task y Harvest. Steps Móvil
(`/truck/`) conserva su plan propio T46: pruebas en terreno, binarios y tiendas
no quedan aprobados por este recorrido.

## Condiciones para considerar una entrega lista

- El formulario usa relaciones a los maestros existentes; los textos históricos
  aparecen solo como referencia. Los centros de costo son cuentas analíticas.
- Una operación y su reintento conservan cantidades/importes y no duplican
  documentos. Un usuario de otra empresa no puede acceder a sus registros.
- Balanzas/impresoras: perfiles generales disponibles; falta homologación con
  modelos físicos. La simulación de USB/Bluetooth no acredita lectura o impresión
  con equipos del cliente.
- Los diarios/cuentas/folios y la política de capitalización se revisan con el
  responsable. No se crean cuentas contables ni se contabilizan documentos
  reales para preparar una demostración.
- Las pantallas históricas no equivalen a una funcionalidad migrada y aceptada.
  Packing anterior y prototipos de Cosecha se conservan separados del flujo nativo.

## Decisiones operativas

Los accesos por IP y puerto apuntan al dominio canónico conservando ruta y query.
Las integraciones usan HTTPS directamente. Los agentes consultan el registro
de ambientes y el código realmente cargado, no una rama abierta por casualidad.
No cierran tickets basándose en análisis o una respuesta HTTP.

Cada publicación conserva commit, versiones, hashes, resultados de pruebas y
respaldo. La producción recibe el paquete comprobado en Desarrollo y aceptado
para ese destino. No se copian bases entre clientes ni se sobrescriben raíces
de addons compartidas. Las instalaciones legadas se conservan fuera del circuito
de publicación; esta revisión no autoriza borrar sus bases ni históricos.

La evidencia de ejecución y los pendientes concretos se registran en el acta
de entrega de esta corrección; este recorrido por sí solo no certifica aceptación.
