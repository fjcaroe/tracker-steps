# Instrucciones para Claude: separar Contratos/Finiquitos y habilitar SimpleDigital

## Texto inicial para Claude

Lee este documento completo y ejecútalo de principio a fin. Primero audita y
confirma el estado actual; después implementa la separación arquitectónica,
migra sin pérdida de datos, despliega en orden y valida en navegador. No des por
terminada la tarea sólo porque los módulos instalen: Contratos y Finiquitos deben
funcionar dentro de la Nómina nueva en Demo-SyS con el motor SimpleDigital y con
la misma experiencia funcional que Desarrollo y Demo.

## Objetivo

Convertir `step_hr_contract_lifecycle` en un núcleo contractual independiente del
motor de nómina y añadir adaptadores explícitos para:

1. la solución agrícola Steps usada en Desarrollo y Demo;
2. `l10n_cl_simpledigital_payroll`, usado en Demo-SyS.

Al finalizar debe existir una única lógica legal y documental para contratos,
adecuación de jornada, avisos de término y finiquitos. Las diferencias de campos,
menús y maestros de cada motor deben resolverse únicamente en sus adaptadores.

Arquitectura requerida:

```text
step_hr_contract_lifecycle              Núcleo común
├── Odoo estándar: hr_contract, hr_payroll, hr_holidays, mail, analytic
├── calendario legal y adecuación de jornada
├── plantillas y documentos laborales
├── contratos y cargas DT
├── avisos de término
├── cálculo y trazabilidad de finiquitos
└── modelos maestros propios y estables

step_hr_contract_lifecycle_agriculture  Adaptador agrícola
├── step_hr
├── l10n_cl_hr
├── fundo/predio y campos agrícolas
└── migración desde maestros agrícolas existentes

step_hr_contract_lifecycle_simpledigital Adaptador SyS
├── l10n_cl_simpledigital_payroll
├── campos previsionales y contractuales SimpleDigital
├── integración con su estructura de Nómina
└── menús y acciones dentro del dashboard Steps Nómina
```

No crees tres copias del mismo módulo ni dupliques fórmulas entre adaptadores.

## Estado actual comprobado

Antes de trabajar, lee:

`C:\Users\tito4\Documents\Odoo\docs\AUDITORIA_HOMOLOGACION_ODOO_2026-08-23.md`

Estado actual:

| Ambiente | Base | Nómina/Libro | Colaciones | Contratos/Finiquitos |
|---|---|---:|---:|---:|
| Desarrollo | `LAB_TAREAS` | 18.0.3.3.0 | 18.0.2.1.0 | instalado |
| Demo | `STEPS_DEMO` | 18.0.3.3.0 | 18.0.2.1.0 | instalado |
| Demo-SyS | `STEPS_DEMO_SYS` | 18.0.3.3.0 | 18.0.2.1.0 | no instalado |

Los tres servicios están activos y las URLs responden HTTP 200.

El intento de instalar el addon actual en Demo-SyS falló correctamente y fue
revertido. La causa no fue la data: fue la arquitectura del addon.

Problemas concretos encontrados:

- El manifest depende de `step_hr` y `l10n_cl_hr`.
- Demo-SyS usa `l10n_cl_simpledigital_payroll`; `step_hr` y `l10n_cl_hr` no están
  instalados en esa base.
- La dependencia forzó la instalación de `l10n_cl_hr` y falló en la vista
  `report_payslip_remove_worked_days`, cuyo XPath busca
  `//div[@id='worked_days_table']`, elemento que no existe en el reporte SyS.
- El núcleo referencia directamente `hr.causal.termino`, `step.fundo`, menús de
  `l10n_cl_hr`, campos como `afp_id` y XML IDs del motor agrícola.
- `security/ir.model.access.csv` referencia
  `l10n_cl_hr.model_hr_causal_termino`.
- `views/menus.xml` usa como padre
  `l10n_cl_hr.menu_cl_hr_payroll_base`.

No soluciones esto instalando a la fuerza los módulos agrícolas en SyS.

## Conexión al servidor

Desde PowerShell en este computador:

```powershell
cd C:\Users\tito4\Documents\Odoo
gcloud auth list
gcloud config get-value project
gcloud compute ssh odoo-new --project=stepsconsulting --zone=us-central1-c
```

Servidor actual: instancia `odoo-new`, proyecto `stepsconsulting`, zona
`us-central1-c`.

Ambientes:

| Ambiente | URL | Base | Código | Configuración | Servicio | Usuario |
|---|---|---|---|---|---|---|
| Desarrollo | `https://desarrollo.stepsapp.cl` | `LAB_TAREAS` | `/opt/dev_odoo18/odoo_agriculture` | `/etc/dev_odoo18.conf` | `odoo18-dev.service` | `odoo` |
| Demo | `https://demo.stepsapp.cl` | `STEPS_DEMO` | `/opt/demo_odoo18/odoo_agriculture` | `/etc/demo_odoo18.conf` | `odoo18-demo.service` | `demo_odoo18` |
| Demo-SyS | `https://demo-sys.stepsapp.cl` | `STEPS_DEMO_SYS` | `/opt/demosys_odoo18/odoo_agriculture` | `/etc/odoo18-demo-sys.conf` | `odoo18-demo-sys.service` | `demosys_odoo18` |

Motor SimpleDigital compartido:

```text
/opt/rrhh/l10n_cl_simpledigital_payroll
```

Puedes inspeccionar y extender esa solución porque estamos autorizados a
adaptarla en nuestro servidor. Evita editar `/opt/rrhh` directamente: implementa
la compatibilidad mediante herencia y adaptadores versionados en nuestros addons.
Así no perdemos cambios cuando SimpleDigital entregue una actualización. Si
encuentras una incompatibilidad imposible de resolver por herencia, documenta la
razón y guarda cualquier parche como código versionado Steps antes de aplicarlo;
nunca hagas un cambio manual sin respaldo dentro de `/opt/rrhh`.

No muestres ni copies claves en la salida. Usa las credenciales locales ya
configuradas.

## Reglas de seguridad y alcance

- No copies ni reemplaces bases de datos entre ambientes.
- Demo-SyS debe conservar sus 29 compañías, 192 empleados, 387 liquidaciones y
  toda la configuración SimpleDigital.
- No desinstales `l10n_cl_simpledigital_payroll`.
- No instales `step_hr` o `l10n_cl_hr` en Demo-SyS para simular compatibilidad.
- No borres tablas, columnas, modelos, XML IDs ni registros existentes.
- No uses IDs de base hardcodeados.
- No hagas `git push`.
- No envíes correos, documentos a la DT, pagos, documentos tributarios ni
  notificaciones reales durante las pruebas.
- Antes de cada escritura verifica que no haya otro despliegue o actualización
  Odoo en ejecución.
- Respalda base y addons antes de cada migración.
- Trabaja primero en el código local de
  `C:\Users\tito4\Documents\Odoo`; el servidor no debe ser la única copia.

## Fase 1: auditoría profunda antes de modificar

### 1.1 Inventario del módulo contractual

Compara el código de `step_hr_contract_lifecycle` en los tres árboles. Los hashes
de fuente deben ser iguales antes de empezar, aunque el addon esté desinstalado
en Demo-SyS.

Inventaría en detalle:

- modelos y campos propios;
- modelos heredados;
- comodels de todos los `Many2one`, `One2many` y `Many2many`;
- XML IDs externos usados en vistas, seguridad, menús, informes y datos;
- accesos directos a campos no estándar;
- métodos que construyen CSV DT;
- cálculos de finiquito y jornada;
- crons y automatizaciones;
- datos existentes en tablas contractuales de Desarrollo y Demo.

### 1.2 Inventario real de SimpleDigital

No supongas nombres por intuición. Revisa su manifest, modelos, vistas, menús,
grupos y campos instalados en `STEPS_DEMO_SYS`.

Identifica al menos:

- modelo y campos reales de contrato;
- institución previsional, salud, APV, CCAF y tipo de jornada;
- causales o estructuras de término existentes;
- campos usados por liquidaciones y promedios de remuneración;
- menú raíz correcto de Nómina;
- vistas de contrato que pueden heredarse sin XPath frágiles;
- reglas multiempresa y grupos de acceso;
- posibles campos equivalentes para cada columna DT.

Genera una tabla de mapeo con cuatro columnas:

| Concepto contractual | Campo del núcleo | Adaptador agrícola | Adaptador SimpleDigital |
|---|---|---|---|

No continúes hasta que la tabla cubra todos los campos consumidos por contratos,
avisos, finiquitos y archivos DT.

## Fase 2: convertir `step_hr_contract_lifecycle` en núcleo común

### 2.1 Dependencias

El núcleo no puede depender de addons agrícolas ni de un proveedor específico.
Usa únicamente dependencias Odoo estándar realmente necesarias, por ejemplo:

```python
"depends": [
    "hr_contract",
    "hr_holidays",
    "hr_payroll",
    "mail",
    "analytic",
]
```

Confirma los módulos exactos requeridos antes de cerrar el manifest.

### 2.2 Maestro propio de causales

El núcleo no puede heredar obligatoriamente `hr.causal.termino` porque ese modelo
no existe en SyS.

Crea un maestro estable, por ejemplo:

```text
step.hr.termination.cause
```

Debe incluir como mínimo:

- código interno;
- código DT;
- artículo/inciso;
- nombre y descripción legal;
- vigencias desde/hasta;
- certificado obligatorio;
- plazo de aviso;
- aplica IAS anual;
- aplica IAS mensual;
- aplica mes de aviso;
- compañía o carácter compartido, según corresponda;
- activo/inactivo.

Migra las relaciones de avisos y finiquitos hacia este maestro. En Desarrollo y
Demo copia de forma idempotente las causales existentes desde
`hr.causal.termino`, preservando referencias y sin borrar el maestro antiguo.

### 2.3 Ubicación de trabajo

El núcleo no puede declarar un campo obligatorio hacia `step.fundo`.

Usa un concepto estándar para la ubicación contractual —preferentemente
`hr.work.location` o un modelo propio neutral si la trazabilidad lo exige—. El
adaptador agrícola puede añadir la relación con fundo/predio y sincronizarla con
la ubicación neutral.

### 2.4 Acceso a datos específicos

No accedas directamente a `contract.afp_id`, `contract.isapre_id` u otros campos
opcionales desde el núcleo.

Implementa una interfaz de adaptación, por ejemplo:

```python
def _steps_contract_payload(self):
    return {...datos estándar...}

def _steps_pension_payload(self):
    return {...}

def _steps_termination_payload(self):
    return {...}
```

Los adaptadores heredan esos métodos y completan la información del motor. Los
generadores DT consumen exclusivamente los payloads normalizados.

No llenes silenciosamente con vacío un dato legal obligatorio. Devuelve una
validación comprensible que indique el campo y empleado/contrato faltante.

### 2.5 Menús y dashboard

El núcleo no debe referenciar XML IDs de `l10n_cl_hr`.

Integra Contratos y Finiquitos dentro de la aplicación Steps Nómina creada por
`step_hr_remuneration_book`. Deben aparecer como secciones internas, no como una
aplicación raíz independiente en el Home.

La portada de Nómina debe ofrecer accesos claros a:

- contratos;
- plantillas laborales;
- adecuación de jornada;
- avisos de término;
- finiquitos;
- cargas DT;
- Libro de Remuneraciones.

Si el dashboard requiere acciones opcionales, resuélvelas mediante XML IDs del
núcleo o capacidades registradas por el adaptador; no compruebes la base por ID.

### 2.6 Seguridad

- Cambia las referencias de acceso desde
  `l10n_cl_hr.model_hr_causal_termino` al modelo propio.
- Conserva separación entre visualización, emisión, aprobación, auditoría y
  datos sensibles.
- Revisa reglas multiempresa para las 29 compañías de SyS.
- Ningún usuario debe ver contratos o finiquitos de otra compañía sin permisos.
- La instalación no debe conceder automáticamente aprobación de finiquitos a
  todos los usuarios de Nómina.

### 2.7 Versiones y migraciones

Incrementa la versión del núcleo, por ejemplo a `18.0.2.0.0`, y crea migraciones
pre/post idempotentes.

Las migraciones deben:

- detectar columnas y modelos existentes antes de operar;
- copiar causales sin duplicarlas;
- mantener documentos, adjuntos y estados;
- conservar referencias de contratos, avisos y finiquitos;
- poder ejecutarse nuevamente sin producir duplicados;
- registrar conteos antes/después;
- abortar con mensaje claro si detectan datos imposibles de mapear.

## Fase 3: adaptador agrícola

Crea `step_hr_contract_lifecycle_agriculture`.

Responsabilidades:

- depender de `step_hr`, `l10n_cl_hr` y el núcleo;
- mapear `step.fundo` a la ubicación neutral;
- mapear AFP, Isapre, tipo de jornada y causales agrícolas;
- migrar/reutilizar datos existentes sin duplicarlos;
- colocar menús adicionales sólo si son realmente agrícolas;
- mantener el funcionamiento actual de Desarrollo y Demo.

No muevas al adaptador cálculos legales, flujos de aprobación, documentos o CSV
que sean comunes.

## Fase 4: adaptador SimpleDigital

Crea `step_hr_contract_lifecycle_simpledigital`.

Responsabilidades:

- depender de `l10n_cl_simpledigital_payroll` y el núcleo;
- mapear los campos reales de contrato y previsión de SimpleDigital;
- obtener promedios y bases de cálculo desde liquidaciones existentes sin
  modificar su motor;
- integrar acciones y menús en Steps Nómina;
- adaptar causales existentes si SimpleDigital tiene un concepto equivalente;
- presentar validaciones de datos incompletos antes de generar documentos;
- funcionar con múltiples compañías;
- no heredar reportes de liquidación mediante el XPath fallido;
- no modificar el cálculo de liquidaciones de SimpleDigital.

Si SimpleDigital tiene un finiquito propio, no dupliques registros. Define una
relación o migración clara y decide qué modelo es la fuente canónica. Documenta
la decisión con evidencia del código y de la data actual.

## Fase 5: pruebas antes de desplegar

### 5.1 Pruebas de código

- compilación Python;
- parseo XML;
- sintaxis JavaScript;
- instalación limpia del núcleo;
- instalación de cada adaptador con su motor correspondiente;
- actualización desde la versión actual en Desarrollo/Demo;
- reinstalación idempotente en una copia de prueba de Demo-SyS;
- ausencia de dependencias cruzadas.

### 5.2 Pruebas legales mínimas

Conserva y amplía pruebas para:

- reducción de jornada 44 → 42 → 40 horas en las fechas legales configuradas;
- contratos que ya cumplen el máximo;
- contratos que requieren lote de adecuación;
- feriado proporcional, incluyendo 15-03-2021 a 17-11-2021 = 8 meses y 2 días;
- fracción superior a seis meses para IAS;
- tope de 11 años/330 días cuando corresponda;
- tope de remuneración aplicable;
- causales con y sin derecho a indemnización;
- sueldo fijo y remuneración variable;
- falta de liquidaciones suficientes;
- vacaciones usadas, pendientes y proporcionales;
- generación DT sin envío.

No declares cumplimiento legal sólo porque un cálculo pase pruebas. Mantén
trazabilidad de fórmula, fuente, fecha y datos usados.

### 5.3 Pruebas con data SyS

En una copia o con operaciones estrictamente no destructivas sobre
`STEPS_DEMO_SYS`, valida:

- lectura de los 192 empleados;
- lectura de las 387 liquidaciones;
- contratos con distintas compañías y estados;
- empleado sin RUT o con campos incompletos;
- cálculo preliminar sin crear asientos ni envíos;
- permisos de un usuario de Nómina normal y un aprobador;
- que no cambien totales de liquidaciones existentes;
- que el Libro de Remuneraciones siga generando su vista previa.

## Fase 6: respaldos y despliegue

### 6.1 Antes de escribir

Comprueba procesos activos:

```bash
ps -eo pid,lstart,cmd | grep -E 'odoo-bin.*(-u|--update)|rsync|scp ' | grep -v grep
```

Crea respaldos nuevos —no reutilices sólo los del 05:00— para cada base y cada
addon afectado. Usa `pg_dump -Fc`, tar de código y SHA-256.

### 6.2 Orden obligatorio

1. Desarrollo:
   - actualizar núcleo;
   - instalar adaptador agrícola;
   - migrar y validar;
   - comprobar navegador y logs.
2. Demo:
   - repetir exactamente el release validado;
   - instalar adaptador agrícola;
   - comprobar navegador y logs.
3. Demo-SyS:
   - desplegar el mismo núcleo;
   - instalar adaptador SimpleDigital;
   - no instalar el adaptador agrícola;
   - validar con data SyS y navegador.

Detén y reinicia únicamente el servicio correspondiente. Ejecuta Odoo con el
usuario propio del ambiente. Si una actualización falla, restaura el código,
levanta el servicio y analiza la transacción antes de reintentar; no encadenes
parches a ciegas.

## Fase 7: validación final en navegador

Usa las sesiones autenticadas existentes o inicia sesión sin exponer claves.
Prueba con recarga completa de assets.

En los tres ambientes valida:

1. Home sin una aplicación raíz independiente llamada Finiquitos.
2. Entrada a Nómina con el layout nuevo, logo Steps y títulos legibles.
3. Selector mensual de Nómina funcionando.
4. Acceso interno a Contratos.
5. Plantillas y generación de documento de prueba.
6. Calendario de reducción de jornada y simulador.
7. Avisos de término.
8. Finiquito en borrador con desglose auditable.
9. Flujo de revisión/aprobación según permisos.
10. Archivo DT generado localmente, sin enviarlo.
11. Libro de Remuneraciones y su selector mensual aún funcionando.
12. Colaciones y su selector mensual sin regresiones.

En Demo-SyS confirma además:

- que el dashboard identifica el motor Steps/SimpleDigital;
- que las liquidaciones históricas mantienen sus totales;
- que los contratos usan los campos reales de SimpleDigital;
- que no aparece el error de XPath `worked_days_table`;
- que no se instalaron `step_hr` ni `l10n_cl_hr`.

Revisa consola, peticiones RPC, logs del servicio y errores de assets. No basta
con que la pantalla abra.

## Criterios de aceptación

La tarea sólo está terminada cuando:

- el mismo núcleo está instalado y en la misma versión en las tres bases;
- Desarrollo y Demo usan únicamente el adaptador agrícola;
- Demo-SyS usa únicamente el adaptador SimpleDigital;
- Contratos y Finiquitos funcionan dentro de Steps Nómina en Demo-SyS;
- las migraciones preservan todos los registros y adjuntos existentes;
- los cálculos legales tienen pruebas y desglose auditable;
- no existe una aplicación Finiquitos independiente en Home;
- los tres servicios quedan activos y HTTP 200;
- no hay nuevos `ERROR`, `CRITICAL` o `Traceback` atribuibles a estos addons;
- Nómina, Libro de Remuneraciones y Colaciones continúan funcionando;
- el código local y el desplegado tienen hashes coincidentes;
- se entrega evidencia y rutas de respaldos.

## Informe de cierre requerido

Crea un MD nuevo en:

```text
C:\Users\tito4\Documents\Odoo\docs\ENTREGA_ADAPTER_CONTRATOS_SIMPLEDIGITAL.md
```

Debe incluir:

- auditoría y tabla de mapeo;
- arquitectura final;
- módulos/versiones creados;
- migraciones y conteos antes/después;
- archivos modificados;
- respaldos y SHA-256;
- comandos de despliegue por ambiente;
- pruebas automatizadas;
- pruebas en navegador con evidencia;
- comparación de totales SyS antes/después;
- errores encontrados y cómo se resolvieron;
- deuda técnica real que permanezca;
- confirmación explícita de que no se hizo `git push` ni se enviaron acciones
  externas.

No ocultes un pendiente bajo la frase “instalación exitosa”. Si algo no funciona
de punta a punta, repórtalo y continúa corrigiendo mientras sea seguro hacerlo.
