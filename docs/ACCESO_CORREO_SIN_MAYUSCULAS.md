# Acceso por correo sin distinción de mayúsculas

Estado al 20-10-2026: instalado y verificado en Desarrollo y Cerro El Plomo. Solicitud del usuario del 20-10-2026, incluida la normalización
a minúsculas de una cuenta específica de Cerro. Los identificadores personales
se conservan en la evidencia privada, fuera del repositorio público.

## Comportamiento

`step_auth_email_casefold` normaliza el correo ingresado antes de llamar a la
autenticación nativa de Odoo. Conserva contraseña, MFA, estado activo, permisos,
empresas y controles de intentos. Los usuarios cuyo login no tiene arroba
mantienen su búsqueda exacta habitual.

Los correos nuevos y las modificaciones explícitas de login se almacenan en
minúsculas. Los existentes no se renombran en lote: la búsqueda resuelve también
los correos históricos escritos con mayúsculas. La comparación SQL es literal;
porcentaje y guion bajo no se interpretan como comodines.

Un índice único parcial sobre `lower(login)` evita identidades duplicadas,
incluidas las cuentas archivadas. Antes de instalar se comprueban duplicados;
si existen, se detiene la instalación sin elegir una cuenta arbitrariamente.
La comprobación previa no encontró duplicados en Desarrollo ni Cerro.

## Pruebas y conservación

Las cuatro pruebas verifican correos nuevos e históricos, caracteres literales,
colisiones al crear/renombrar/archivar, protección SQL, contraseña correcta e
incorrecta, cuentas inactivas y usuarios que no son correos.

La primera prueba de sesión dentro de HttpCase llegó a autenticar, pero quedó
bloqueada por la combinación del cursor de prueba con la sesión HTTP. Esa copia
fallida no acredita la entrega. La comprobación HTTP definitiva usa una copia
privada y un usuario sintético confirmado en su propia transacción. No sustituye
la validación de contraseña. Comprueba tres combinaciones de mayúsculas, rechazo
de contraseña incorrecta y de cuenta inactiva, con el formulario real de login.
Luego detiene el proceso HTTP local y retira exclusivamente su usuario y sus
registros de dispositivo/login de prueba. Se exige que las tablas originales
queden idénticas al snapshot previo.

La prueba de Cerro incluye la normalización transaccional de la cuenta solicitada
con los datos reales de su copia. Se compara todo el registro salvo login y la
fecha/autor de escritura, y se comparan empresas y grupos. Las credenciales no
se imprimen. El aviso nativo de seguridad por el cambio de login se conserva cancelado antes
del commit; no se envía correo ni se alteran avisos de cambios posteriores. La copia
revierte esa operación después de probarla.

## Publicación

El publicador `email-login` está restringido a Desarrollo y Cerro. Usa el paquete
inmutable probado, overlays privados, respaldo de base/configuración/filestore,
bloqueo `/run/lock/steps-environments.lock`, ausencia de downgrade y comprobación
de modificaciones concurrentes. Las tablas de usuarios, claves API, grupos y
empresas se incluyen en la conservación por huellas, sin exponer sus contenidos.

La normalización autorizada de Cerro usa los argumentos `--normalize-user-id`
y `--expected-user-login`. Solo se permite en compatibilidad y publicación de
Cerro para este tipo de paquete. En la copia hace rollback; en producción corre
bajo el mismo respaldo y bloqueo, después de instalar y comprobar el paquete.
No reemplaza la contraseña ni crea otra cuenta. El cambio de login invalida
naturalmente las sesiones cuya firma incluía el identificador anterior.

Las pruebas HTTP con contraseñas sintéticas solo se ejecutan en bases
`MANAGEMENT_QA_`. En los destinos se verifica el módulo instalado, su origen,
el índice validado, la vista y menú nativos de usuarios y la resolución de ambas
formas para todas las identidades de correo, sin pedir ni usar contraseñas reales.

La evidencia privada está en `~/.codex/local-artifacts/login-correo-20261020/`.

## Paquete y entrega de Desarrollo

Paquete: commit `d846b4265db980b4509b0dbb87f717ddb98e2743`, SHA-256
`0c9ea7ef6bcb89d8827fc2b7375057d4c4432263df70ad3dc72c4ea2a7931ea1`.
Versión `18.0.1.0.0`, seis archivos de módulo.

La copia `MANAGEMENT_QA_DEVELOPMENT_email3` pasó las cuatro pruebas, la
comprobación de cinco identidades existentes y las cinco condiciones HTTP
reales (tres variantes de correo, contraseña incorrecta y cuenta inactiva).
Se eliminaron los fixtures y coincidió la conservación de los registros.
Prueba: `/opt/steps-validation/management_development_email3/qa_passed.json`.

Se publicó ese paquete en Desarrollo con respaldo
`/opt/steps_backups/management_development_20261020T173610Z` y overlay
`/opt/steps-managed/releases/development/d846b4265db980b4509b0dbb87f717ddb98e2743/`.
La comprobación posterior confirmó versión, origen, índice, vistas y las cinco
identidades; el servicio quedó activo y la URL HTTPS de login respondió.

La primera copia de Cerro con paquete final pasó las cuatro pruebas, doce
identidades y el HTTP real. El ensayo de la normalización detectó el aviso
nativo de seguridad que ignora los flags de tracking. Se ajustó exclusivamente
el procedimiento de esa operación cosmética para conservar su aviso cancelado
antes del commit; no se cambia la generación de avisos de seguridad posteriores.
La prueba final usa otra copia fresca, sufijo `email4`.

## Entrega de Cerro y cierre

La copia fresca `MANAGEMENT_QA_CERRO_email4` pasó las cuatro pruebas, las doce
identidades de correo existentes, las cinco condiciones HTTP y la normalización
transaccional de la cuenta solicitada. Conservó los registros originales y
revirtió esa normalización de ensayo. Prueba del mismo paquete:
`/opt/steps-validation/management_cerro_email4/qa_passed.json`.

Se publicó el paquete probado en Cerro con respaldo
`/opt/steps_backups/management_cerro_20261020T174408Z` y overlay
`/opt/steps-managed/releases/cerro/d846b4265db980b4509b0dbb87f717ddb98e2743/`.
El servicio `odoo18-cerroelplomo.service` quedó activo. La verificación posterior
confirmó versión, origen, índice, vista/menú nativos y las doce identidades.
El formulario de <https://cerroelplomo.stepsapp.cl/web/login> respondió 200 y
contiene los campos nativos de correo y contraseña.

La cuenta específica quedó almacenada en minúsculas. El comparador confirmó que
su contraseña, estado, empresas, grupos y los demás campos originales quedaron
iguales, salvo login y fecha/autor de esa escritura. El aviso nativo de ese cambio
cosmético se conservó cancelado antes del commit. No se envió correo ni se
alteraron los avisos de seguridad de operaciones posteriores.

La revisión final volvió a leer la cuenta y confirmó que sigue activa e interna
y mantiene su empresa. La evidencia privada conserva el identificador y correo
exactos. No se solicitó ni se utilizó su contraseña real: la autenticación con
contraseñas se probó únicamente con los usuarios sintéticos retirados de las
copias privadas. El usuario puede volver a ingresar con su contraseña habitual.

Los logs finales son `development-qa.log`, `development-deploy.log`, `cerro-qa.log`
y `cerro-deploy.log` en el directorio privado indicado. El cierre conserva las
pruebas de paquete y la verificación de entrega, sin incluir datos personales en
el repositorio público.
