# Almacenamiento privado de Titulación

El módulo selecciona el backend sin modificar `settings.py`:

- Si existen `SUPABASE_URL` y `SUPABASE_SECRET_KEY`, utiliza el bucket privado
  `titulacion-privado`.
- También acepta `SUPABASE_SERVICE_ROLE_KEY` para proyectos que todavía usan
  la clave legacy.
- Si no existen, utiliza `media/titulacion` para desarrollo local.

Variables opcionales:

```env
TITULACION_STORAGE_BACKEND=auto
SUPABASE_URL=https://PROYECTO.supabase.co
SUPABASE_SECRET_KEY=sb_secret_CLAVE_SOLO_DEL_SERVIDOR
```

No se debe usar una clave `sb_publishable_...` para este backend. La clave
secreta nunca debe enviarse al navegador, compartirse por chat ni confirmarse
en Git. Las descargas validan primero el alcance del proyecto y generan un
enlace firmado de corta duración.

El SQL idempotente aplicado al esquema se conserva en
`apps/titulacion/sql/001_storage_archivos.sql`.

La subida de evidencias por tutoría sigue perteneciendo a
`apps/seguimiento`; Titulación solo consume su resumen cuando Persona 3 exponga
el servicio acordado.
