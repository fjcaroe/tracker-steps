# Steps Colaciones

Aplicación Odoo 18 para registrar, planificar y valorizar colaciones de
trabajadores. Reemplaza el prototipo construido en Studio por modelos,
seguridad, reglas y vistas versionadas.

## Flujo operativo

1. Marcar productos con **Es colación**.
2. Marcar proveedores con **Es proveedor de colaciones**.
3. Habilitar trabajadores y configurar código de credencial, NIP o NFC.
4. Crear una tarifa, agregar productos y activarla.
5. Configurar un tótem con producto, proveedor y método de identificación.
6. Registrar manualmente o desde la URL del tótem.
7. Validar los registros para congelar la tarifa y el costo aplicable.

La base impide que un trabajador reciba dos veces el mismo producto de
colación durante el mismo día, incluso si los registros llegan desde distintos
tótems.

## Aplicación de tótem

El formulario del tótem es una PWA instalable. Después de abrirlo al menos una
vez con conexión puede cargar su interfaz sin red. Las marcaciones offline se
guardan en el navegador y se transmiten cuando vuelve la conexión, usando un
UUID por evento para que los reintentos sean idempotentes.

NFC admite dos formas:

- lector USB configurado como teclado, recomendado para tótems fijos;
- Web NFC cuando el dispositivo y el navegador lo permiten.

El modo offline no elimina las reglas del servidor: al sincronizar se vuelven a
validar trabajador, producto, fecha, antigüedad y duplicidad.

## Migración desde Studio

El `post_init_hook` detecta de forma defensiva los modelos usados en QA:

- `x_tarifa_colaciones` y sus líneas;
- `x_registro_colaciones` y sus líneas;
- `x_plan_colaciones` y sus líneas;
- campos Studio de productos y trabajadores.

La migración usa referencias de origen únicas, por lo que puede reintentarse
sin duplicar registros. Cuando detecta la aplicación Studio, oculta su menú
raíz después de migrar y conserva intactas las tablas originales.

## Seguridad

- `Colaciones / Usuario`: registros e informes.
- `Colaciones / Administrador`: validación, planificación, tarifas, tótems y
  configuración de maestros.
- Las reglas de registro respetan las empresas activas.
- Los registros guardan solo una versión enmascarada del identificador usado;
  no duplican el NIP ni el UID NFC.
