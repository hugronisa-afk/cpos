# CPOS UTB - Maquetación adaptada a Django

Este proyecto conserva la estructura Django original y adapta la maqueta HTML/CSS dentro de las apps existentes:

- `apps.accounts`: login, usuarios/roles y bitácora básica.
- `apps.titulacion`: panel principal, expediente, proyecto, artículo, aprobaciones y requerimientos.
- `apps.seguimiento`: panel de seguimiento, tutorías, evidencias y reportes.

## Rutas principales

- `/` Landing institucional.
- `/login/` Inicio de sesión con `LoginView` de Django.
- `/usuarios/` Administración visual de usuarios, roles, programas y cohortes.
- `/auditoria/` Bitácora visual de acciones.
- `/titulacion/` Panel principal.
- `/titulacion/expediente/` Expediente.
- `/titulacion/proyecto/` Proyecto.
- `/titulacion/articulo/` Artículo científico.
- `/titulacion/aprobaciones/` Aprobaciones.
- `/titulacion/requerimientos/` Requerimientos.
- `/seguimiento/` Panel de seguimiento.
- `/seguimiento/tutorias/` Tutorías.
- `/seguimiento/evidencias/` Evidencias.
- `/seguimiento/reportes/` Reportes.
- `/estado-db/` Vista de prueba de conexión a PostgreSQL.

## Nota

Las pantallas todavía usan datos temporales para visualizar el sistema. La estructura queda lista para conectar modelos, consultas ORM, permisos por rol y formularios reales.
