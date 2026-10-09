# Piloto Android de Steps App — 09-10-2026

Aplicación unificada con ingreso propio, empresas, Colaciones, Movilización y
Tracker. El piloto nativo apunta a `https://desarrollo.stepsapp.cl/steps_app/v1`.
El aviso visible recuerda usar datos de prueba. Crear una cuenta no concede
acceso a una empresa: su administrador debe aprobarla y asignarle los roles.
Tracker conserva su ingreso y servidor propios; no se habilita automáticamente.

## Android

- Identificador reservado en Play Console: **`comm.stepsapp.mobile`**. Se corrigió
  el paquete anterior `cl.stepsapp.movil`, que Google rechazó por no coincidir.
  El namespace Java se conserva; el bundle iOS existente sigue separado.
- Versión comercial `2.0.0-beta.1`; códigos crecientes por ejecución de CI.
- Android 8+ (API 26), compile/target API 36, AGP 8.10.1, Gradle 8.11.1, Java 21.
- Lector nativo `@capacitor/barcode-scanner` 2.2.6 con ZXing y permiso de cámara;
  la entrada manual sigue disponible. Se descartan resultados de escaneos
  cancelados y de pantallas desmontadas.
- Iconos Steps y área de contenido protegida de barras y recortes del sistema.
- La firma se hace localmente con `tools/android/sign_release.py`. La clave de
  subida, su contraseña y los binarios quedan fuera de Git, en almacenamiento
  privado del operador. Conservar una copia segura de la clave para actualizaciones.

## Evidencia y servidor

La ejecución [37957806572](https://github.com/fjcaroe/tracker-steps/actions/runs/37957806572)
pasó 171 pruebas del cliente y compiló APK/AAB. La instalación y el arranque de
esa compilación pasaron en Android 16 mediante
[37959159854](https://github.com/fjcaroe/tracker-steps/actions/runs/37959159854).
La captura reveló la superposición de la barra del sistema, corregida en el
paquete final. La comprobación nativa final está en
[37959794042](https://github.com/fjcaroe/tracker-steps/actions/runs/37959794042).
Esto no certifica cámara, GPS, teclado ni actualización de datos en un teléfono físico.

El portal se empaqueta desde un commit con hashes de todos los archivos mediante
`tools/mobile_ops/build_portal_release.py`; `manage_portal.py` solo permite el
Desarrollo del registro canónico (`LAB_TAREAS`, 8075). Usa una copia nueva,
correo/cron desactivados en ella, pruebas funcionales y comprobación de los
registros originales de 19 tablas. El despliegue emplea el mismo paquete probado,
respaldo, bloqueo compartido y un overlay privado. Comprueba versiones, menús y
formularios antes de reiniciar el servicio. La configuración y las claves no
se registran en Git ni se imprimen.

El primer paquete del servidor (`f27d5bf`) pasó 59 pruebas sin fallos y se instaló
en Desarrollo. El ajuste para administradores (`fc8b0af`, versión 18.0.1.0.2)
pasó 60 pruebas en una copia nueva y también se instaló. Se comprobó el menú y se
abrió el formulario real de accesos con el administrador vigente, sin guardar
registros ficticios. El servicio y la API HTTPS están activos. No concede derechos
a usuarios internos comunes ni cambia sus empresas permitidas.

## Instalación y alcance

En Play Console se habilitó una lista de un participante con el correo facilitado
por el usuario. El correo queda en Play Console, no en este documento público.
El enlace de incorporación se activa cuando se publique la prueba interna.
La ficha pública y el acceso a producción siguen siendo pasos separados; la
consola exige la prueba cerrada de 12 participantes durante 14 días.

Primero instalar, crear la cuenta con una contraseña propia y solicitar acceso
con el código de empresa de Desarrollo. Aprobar la solicitud desde **Steps App →
Accesos** en Odoo y asignar roles mediante su asistente; para conductor/persona,
vincular explícitamente el chofer/empleado correcto. No inferir relaciones por
correo o nombre. El correo saliente y Google/Apple no están habilitados; la
verificación y recuperación manuales están auditadas en Odoo.

Apple Watch conserva el acompañante de la beta iOS (contexto, módulos y pendientes);
su instalación firmada y validación física siguen pendientes. Véase
[STEPS_APP_IOS_WATCH_BETA.md](STEPS_APP_IOS_WATCH_BETA.md).
