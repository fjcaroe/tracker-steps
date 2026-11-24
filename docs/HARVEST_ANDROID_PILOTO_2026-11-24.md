# Harvest — piloto Android, 24-11-2026

Estado: paquete final certificado y publicado en Desarrollo. APK instalado y
probado en emulador Android; pendiente aceptación con usuario y teléfono físico.

## Entrega

- Frontend: Harvest 0.0.7, `stepconsulting/step_harvest`, rama canónica `main`,
  commit `b33d09e8ea7c0631b1a974c11bba6b4f741f189e`.
- Android: Harvest TEST 0.1.0-test (1), paquete `cl.stepsapp.harvest.test`,
  Android 8+ (min 26), compilación/target 36, instalación directa por APK.
- APK validado: `harvest-desarrollo-0.1.0-test.apk`, SHA256
  `b9f750741ebf47725d3a5b73b06e721a95913c59afef6260503b76468127853a`.
- El APK carga `https://desarrollo.stepsapp.cl/cosecha/` y conserva la sesión
  nativa Odoo en su WebView. Su código Android procede del commit `5f2fb9fc`;
  las mejoras posteriores del frontend se sirven desde Desarrollo.
- Paquete web final SHA256:
  `d8e90956d6ac18d22bdcf7faaf14d98ed25402abd218e8d2cad66ce3b0968de4`.
- Backend conservado: `a195985a3dbc064e44836c401d95394f89aa51c9`,
  `step_harvest_launcher` 18.0.1.2.1 y `step_cosecha_operations` 18.0.1.2.0.

Los APK, manifiestos, registros de emulador y paquetes locales están fuera del
checkout, en `~/.codex/local-artifacts/harvest-android-pilot-20261124/`.

## Correcciones

La espera entre entregas usa la fecha y milisegundos del evento. La entrega y
el total de la tarja se guardan juntos antes de anunciar éxito. Los errores de
almacenamiento conservan el formulario y la cola; una confirmación local
fallida puede reintentarse con el mismo UUID sin duplicar la entrega en Odoo.

Al volver desde otra aplicación, el formulario permanece montado y bloqueado
durante la comprobación de sesión. Un cambio de identidad separa los datos.
La transición de OT local a nativa usa el `work_order_id` confirmado para el
UUID enviado. Conserva tarja, selección y totales al recargar, incluso con
referencias de texto duplicadas; no vincula documentos por su nombre.

El piloto ofrece captura manual y folios ingresados por el operador. Sus
pantallas explican el alcance de cámara QR, NFC y balanza Bluetooth. El
contenedor limita navegación y recursos a HTTPS Desarrollo, desactiva acceso
a archivos y contenido, cookies de terceros y copias de seguridad; solicita
únicamente permiso de Internet. El proxy local de desarrollo usa también el
dominio canónico y comprueba TLS.

## Validación realizada

- 41 pruebas unitarias del frontend y compilación TypeScript/Vite aprobadas.
- Dos pruebas Chrome: conservación del formulario al revalidar y transición
  local → sincronización → recarga con referencias duplicadas.
- Dos pruebas JVM, lint y compilación del APK aprobados; firma APK v2 válida.
- Tres pruebas de instrumentación en Android 16/API 36: ajustes de seguridad,
  continuidad de WebView en rotación/segundo plano y permiso de Internet.
- Una prueba Android de conexión real: carga HTTPS de Harvest y acceso al
  formulario nativo de Odoo, sin leer ni ingresar credenciales.
- 15 pruebas de guardas operativas y rutas de publicación aprobadas.
- Primera copia aislada: entrega sobre OT existente, reintento sin duplicados,
  rechazo de contexto alterado, creación de nueva OT con maestros nativos,
  lectura en el panel Odoo, cambio de empresa con cola conservada, selector
  de cuartel por centro y formulario nativo de tarifas. Ese recorrido detectó
  y originó la corrección final de asociación local/nativa.

La certificación y revisión del paquete final se registran en
`/opt/steps-validation/management_development_harvestandroid_b33d09e8/`.
Los respaldos, sesiones retiradas y comprobaciones de publicación quedan en
las evidencias privadas del servidor.

El paquete final se probó con corte real de red en Chrome, captura local,
reconexión, dos entregas separadas por la latencia, cambio de empresa y retorno.
Se sincronizó una OT nueva con cuartel y se recargó la app: conservó la OT
correcta, tarja abierta, 4 cajas, 25 kg y cero pendientes. Se revisaron además
los tres modos de ubicación y el formulario nativo de tarifas. El smoke nativo
del mismo paquete volvió a comprobar contexto inválido, alta única y reintento.

La publicación usó respaldo
`/opt/steps_backups/harvest-web-development-20261124T193234Z`, bloqueo compartido
y comprobación de concurrencia y backend. Los cinco archivos HTTPS coinciden
con el manifiesto; JavaScript servido SHA256
`f7fa4a6464eaa1d2be2c80bddb2a199e1c5b8a3b564f4323d66f4788f989c519`.
Las sesiones temporales y las dos bases privadas de prueba se retiraron,
conservando dumps, filestores y evidencias. El test Android de conexión y login
se repitió después de publicar y pasó. La compilación automática de `main`
también pasó en GitHub Actions, ejecución `45469796417`.

## Aceptación del participante

Falta confirmar el usuario existente y la empresa del participante, y ejecutar
su recorrido en el teléfono físico. La revisión técnica utiliza un perfil
interno existente en la copia, sin cambiar credenciales, grupos o empresas.

El inicio requiere conexión para verificar identidad. Se puede continuar
capturando sin red durante una sesión abierta. Cada instalación conserva su
cola; evitar desinstalarla o borrar sus datos con pendientes sin sincronizar.
Las firmas debug de CI y del equipo local pueden diferir; mantener la misma
firma para actualizar la instalación del piloto. Las descargas `blob:` están
pendientes en el contenedor y se realizan desde la instalación web original.

La auditoría de dependencias aplicó correcciones compatibles. Quedan cuatro
avisos del árbol heredado (Vite/esbuild de desarrollo y React Router legado);
el piloto sirve archivos estáticos compilados y monta `HarvestGate` directamente.
Una actualización mayor de esas herramientas se evalúa en su propia revisión.

La guía de instalación y aceptación está en `docs/ANDROID_PILOTO.md` del
repositorio Harvest.
