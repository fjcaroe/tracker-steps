# Manual breve — Movilización

## Operador / despachador

1. **Maestros**: cargar transportistas (`Movilización → Maestros →
   Transportistas`, marcar "¿Transporte de personal?"), choferes (marcar
   "¿Chofer?" y su transportista), vehículos habilitados (marcar "Habilitado
   para movilización de personal" en la ficha del vehículo, con mínimo/máximo
   de pasajeros) y recorridos con sus paradas.
2. **Tarifas**: `Tarifas y recorridos`, crear una lista con "¿Es
   movilización?" activo, el transportista, y una línea por recorrido con
   tipo de tarifa (fija/por pasajero/mínima/proporcional), sentido y
   vigencia.
3. **Viaje**: `Operación → Viajes / Registro`, crear en borrador, `Abrir`
   (valida inspección/documentos bloqueantes del vehículo/chofer/transportista
   automáticamente), registrar pasajeros (manual o vía la marcación de la
   app móvil una vez integrada), `Cerrar`, `Validar`.

## Costeo

`Operación → Costeo`: sólo visible para el grupo Costeo. Sobre un viaje
validado, `Costear` calcula el costo por pasajero según la tarifa vigente;
`Devolver a validado` limpia el costeo sin duplicar líneas si se recalcula.

## Contabilización

`Operación → Contabilización`: sólo grupo Contabilización. Requiere diario y
cuentas de Movilización configurados en `Configuración → Movilización →
Contabilidad`. Un viaje sólo se contabiliza una vez; la reversa se hace por
mecanismos contables estándar (nota de crédito/reversa del asiento), nunca
borrando el asiento.

## Contratos

`Contratos y cumplimiento → Contratos`: crear con transportista, vigencia y
recorridos; requiere una plantilla ya **validada por legal/prevención**
(`Maestros → Plantillas → Contratos`). `Emitir PDF` congela las tarifas
vigentes en ese momento — cambios posteriores de tarifa no alteran el PDF ya
emitido.

## Prevención de riesgos

- **Derecho a Saber**: un registro por chofer, sobre una plantilla validada;
  `Emitir` deja el registro inmutable.
- **Entrega de EPP**: registrar ítems entregados por chofer, con evidencia.
- **Documentos**: cargar por transportista/chofer/vehículo/contrato según
  los tipos configurados en `Configuración → Reglas de cumplimiento`; los
  marcados "bloqueante" impiden abrir un viaje si están vencidos o sin
  aprobar.
- **Inspecciones**: elegir plantilla, marcar cada ítem Sí/No/No aplica; un
  "No" en un ítem crítico rechaza la inspección y bloquea abrir viajes con
  ese vehículo hasta una nueva inspección aprobada.

## Chofer (app móvil)

La app no tiene interfaz Odoo backend — el chofer nunca ve el backend. El
flujo (vía la API `/mobilization/v1`, ver `step_mobilization/controllers/`):
un operador genera un código de emparejamiento de un solo uso
(`Configuración → Dispositivos móviles → Generar código`), el chofer lo
ingresa una vez en la app para asociar su dispositivo, luego abre sesión
eligiendo vehículo/recorrido, marca pasajeros por PIN/código/NFC, y cierra
al bajar el último pasajero (automático u obligando confirmación según
`Configuración → Aplicación móvil/GPS`).

## Limitaciones conocidas de esta entrega

- No existe todavía un cliente móvil/PWA real — sólo la API backend,
  probada a nivel de lógica (ver `03_PRUEBAS_Y_EVIDENCIA.md`).
- El ícono de la aplicación es un placeholder reutilizado de `step_hr`
  (`static/description/icon.png`); pendiente de un ícono propio.
- La acción "Tarifas Contratistas" de `step_hr` puede mostrar tarifas de
  movilización mezcladas si `step_mobilization` está instalado (se quitó el
  filtro `moviliza=False` para que `step_hr` no dependa de un campo que ya
  no declara — ver `02_ARQUITECTURA_Y_DECISIONES.md`).
