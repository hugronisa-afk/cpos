/*
CPOS - FASE 2
Rol técnico protegido para tres administradores/desarrolladores.
No concede permisos de aprobación académica.
*/

BEGIN;

ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS ck_usuarios_nombre_usuario_formato;

ALTER TABLE cpos.usuarios
    ADD CONSTRAINT ck_usuarios_nombre_usuario_formato
    CHECK (
        nombre_usuario = upper(nombre_usuario)
        AND nombre_usuario ~ '^[0-9]+-(MST|TTR|COR|SUP|ADM)$'
    );

INSERT INTO cpos.roles (
    nombre,
    descripcion,
    nivel_autoridad,
    esta_activo,
    fecha_actualizacion
)
VALUES (
    'administrador_desarrollador',
    'Administración técnica, importación de usuarios y mantenimiento. Sin autoridad académica.',
    'supervision',
    true,
    now()
)
ON CONFLICT (nombre) DO UPDATE SET
    descripcion = EXCLUDED.descripcion,
    nivel_autoridad = EXCLUDED.nivel_autoridad,
    esta_activo = true,
    fecha_actualizacion = now();

INSERT INTO cpos.permisos (
    codigo,
    nombre,
    modulo,
    descripcion,
    esta_activo,
    fecha_actualizacion
)
VALUES
    ('IMPORTACION_USUARIOS', 'Importar usuarios', 'mantenimiento', 'Validar e importar cuentas desde CSV o XLSX.', true, now()),
    ('MANTENIMIENTO_VER', 'Ver mantenimiento', 'mantenimiento', 'Consultar diagnósticos técnicos seguros.', true, now()),
    ('MANTENIMIENTO_EJECUTAR', 'Ejecutar mantenimiento', 'mantenimiento', 'Ejecutar acciones de mantenimiento previamente autorizadas.', true, now())
ON CONFLICT (codigo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    modulo = EXCLUDED.modulo,
    descripcion = EXCLUDED.descripcion,
    esta_activo = true,
    fecha_actualizacion = now();

INSERT INTO cpos.rol_permiso (rol_id, permiso_id)
SELECT rol.id, permiso.id
FROM cpos.roles AS rol
CROSS JOIN cpos.permisos AS permiso
WHERE rol.nombre = 'administrador_desarrollador'
  AND permiso.codigo IN (
      'USUARIO_VER',
      'USUARIO_CREAR',
      'USUARIO_EDITAR',
      'USUARIO_DESACTIVAR',
      'ROL_VER',
      'PERMISO_VER',
      'PROGRAMA_VER',
      'PROGRAMA_CREAR',
      'PROGRAMA_EDITAR',
      'COHORTE_VER',
      'COHORTE_CREAR',
      'COHORTE_EDITAR',
      'MAESTRANTE_VER',
      'MAESTRANTE_CREAR',
      'MAESTRANTE_EDITAR',
      'TUTOR_VER',
      'TUTOR_CREAR',
      'TUTOR_EDITAR',
      'BITACORA_VER',
      'IMPORTACION_USUARIOS',
      'MANTENIMIENTO_VER',
      'MANTENIMIENTO_EJECUTAR'
  )
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

COMMIT;

SELECT
    rol.nombre,
    rol.nivel_autoridad,
    array_agg(permiso.codigo ORDER BY permiso.codigo) AS permisos
FROM cpos.roles AS rol
LEFT JOIN cpos.rol_permiso AS rp ON rp.rol_id = rol.id
LEFT JOIN cpos.permisos AS permiso ON permiso.id = rp.permiso_id
WHERE rol.nombre = 'administrador_desarrollador'
GROUP BY rol.id;
