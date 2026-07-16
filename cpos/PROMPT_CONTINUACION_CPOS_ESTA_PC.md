# Prompt actualizado para continuar CPOS en esta computadora

Quiero que continúes el desarrollo de mi sistema CPOS basándote en el manual original, el plan funcional existente y el estado real del repositorio en esta computadora.

## Fuentes y rutas autoritativas

- Manual original: `C:\Users\Dell\Downloads\Manual Resumido.docx`
- Plan completo de fases 1 a 10: `C:\Users\Dell\.codex\attachments\736e7015-c137-4c3a-984e-932cb13f552a\pasted-text.txt`
- Raíz real del repositorio Git: `C:\Users\Dell\Documents\ISAAC\ProyectoU`
- Proyecto Django y ubicación de `manage.py`: `C:\Users\Dell\Documents\ISAAC\ProyectoU\cpos`
- Python del entorno virtual: `C:\Users\Dell\Documents\ISAAC\ProyectoU\venv\Scripts\python.exe`
- Archivo de variables privadas: `C:\Users\Dell\Documents\ISAAC\ProyectoU\cpos\.env`
- Repositorio remoto: `https://github.com/hugronisa-afk/cpos.git`
- Rama de trabajo de esta computadora: `persona1-accounts`

Lee completamente el manual y el plan de fases antes de modificar código. Si existe alguna contradicción, aplica este orden de prioridad:

1. El estado real y verificable del código y la base de datos.
2. El manual original.
3. Las instrucciones de este prompt actualizado.
4. El plan de fases adjunto.

## Estado Git verificado en esta computadora

- La rama activa es `persona1-accounts`.
- Los cambios publicados en `origin/main` ya fueron integrados localmente mediante avance rápido y sin conflictos.
- En la última comprobación, `HEAD` y `origin/main` estaban en el commit `d646a84`.
- La rama local `persona1-accounts` estaba un commit por delante de `origin/persona1-accounts` debido a esa actualización desde `main`.
- El árbol de trabajo estaba limpio.
- `manage.py check` terminó sin problemas.

Este estado puede haber cambiado desde la última comprobación. Antes de editar:

1. Ejecuta `git status --short --branch` desde la raíz Git.
2. Confirma la rama activa y revisa el historial reciente.
3. No descartes, sobrescribas ni reviertas cambios locales.
4. Si hay cambios nuevos en `origin/main`, intégralos de manera segura en `persona1-accounts`, revisando antes el estado local.
5. No uses `git reset --hard`, `git checkout --`, limpieza destructiva ni force-push.
6. No cambies de rama ni publiques commits salvo que yo lo solicite expresamente.

## Forma correcta de ejecutar Django

Los comandos Django deben ejecutarse desde:

`C:\Users\Dell\Documents\ISAAC\ProyectoU\cpos`

Usa siempre el intérprete del entorno virtual mediante su ruta absoluta. Por ejemplo:

```powershell
cd C:\Users\Dell\Documents\ISAAC\ProyectoU\cpos
C:\Users\Dell\Documents\ISAAC\ProyectoU\venv\Scripts\python.exe manage.py check
C:\Users\Dell\Documents\ISAAC\ProyectoU\venv\Scripts\python.exe manage.py test
```

No supongas que el entorno virtual está dentro de la carpeta `cpos`: se encuentra un nivel arriba, dentro de `ProyectoU\venv`.

## Reglas de trabajo

- Analiza el código, PostgreSQL/Supabase y los datos reales antes de modificar.
- Conserva las fases ya implementadas; no reconstruyas el sistema desde cero.
- Empieza únicamente por la Fase 6 descrita en el plan adjunto.
- Trabaja fase por fase y no avances automáticamente a la Fase 7.
- No me preguntes por decisiones menores. Resuelve con criterio técnico, el manual y la estructura existente.
- Pregunta solamente si existe un bloqueo que requiera información externa o una decisión académica que no pueda inferirse con seguridad.
- Respeta los cambios de mis compañeros y evita editar módulos ajenos cuando no sea necesario para la fase.
- No crees datos académicos ficticios permanentes.
- Las pruebas con datos deben ser reversibles y demostrar que no dejaron residuos.
- Todo SQL nuevo debe ser idempotente y tener rollback correspondiente.
- No muestres ni publiques secretos del archivo `.env`.
- No alteres automáticamente los registros académicos heredados ni las ocho tutorías vencidas sin evidencia o autorización humana.
- Mantén la separación de permisos entre maestrante, tutor, coordinador, supervisor y administrador/desarrollador.

## Estado funcional que debes respetar

Las fases 1 a 5 se consideran implementadas. Antes de aceptarlo ciegamente, contrasta el plan con el código, las tablas y las pruebas actuales. El plan detallado de estas fases y de las fases 6 a 10 está en el archivo adjunto indicado arriba.

La Fase 6 debe cubrir completamente:

- asistencia independiente de tutor y maestrante;
- transiciones válidas de las tutorías;
- grabaciones mediante enlace HTTPS o archivo privado;
- evidencia obligatoria y versionada por tutoría realizada;
- revisión, observación, validación y rechazo de evidencias;
- historial, permisos, auditoría y descargas privadas;
- correspondencia uno a uno entre ocho tutorías realizadas y ocho evidencias validadas;
- paneles y acciones correctas por rol;
- SQL idempotente y rollback, previsiblemente con número 14.

No modifiques automáticamente la situación heredada descrita en el plan: el proyecto real continúa en revisión y las ocho tutorías antiguas vencidas requieren una decisión académica humana.

## Verificación obligatoria de la Fase 6

Al terminar ejecuta, como mínimo:

- `manage.py check`;
- suite completa de pruebas;
- pruebas específicas de la Fase 6 y de permisos por rol;
- compilación o renderizado de plantillas relevantes;
- `git diff --check`;
- inspección de tablas, restricciones y permisos reales de PostgreSQL;
- comprobaciones de páginas para maestrante, tutor, coordinador y supervisor;
- un recorrido reversible cuando corresponda;
- confirmación de que no quedaron datos ficticios.

## Informes durante el trabajo

Primero entrégame una actualización breve indicando:

- qué parte de la Fase 6 ya existe;
- qué brechas reales encontraste;
- qué datos reales están presentes;
- qué vas a corregir.

Luego implementa la Fase 6 completa sin detenerte por decisiones menores. Al terminar explícame:

- qué existía antes y qué cambió;
- cómo funciona ahora;
- ventajas, limitaciones y problemas encontrados;
- archivos modificados;
- tablas, restricciones y permisos añadidos;
- pruebas ejecutadas y sus resultados;
- estado de los datos reales;
- cualquier registro heredado que necesite decisión humana.

No avances a la Fase 7. Espera a que yo diga: `siguiente fase`.
