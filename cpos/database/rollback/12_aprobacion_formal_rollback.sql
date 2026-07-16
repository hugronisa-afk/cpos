/* Reversión de la fase 4. Elimina el historial formal creado por esta fase. */

BEGIN;

DELETE FROM cpos.aprobaciones
WHERE referencia_tabla = 'pasos_aprobacion';

INSERT INTO cpos.aprobaciones (
    proyecto_id, tipo_aprobacion, referencia_tabla, referencia_id, estado
)
SELECT proyecto.id, 'proyecto', 'proyectos_titulacion', proyecto.id, 'pendiente'
FROM cpos.proyectos_titulacion proyecto
WHERE proyecto.estado = 'en_revision'
  AND NOT EXISTS (
      SELECT 1 FROM cpos.aprobaciones aprobacion
      WHERE aprobacion.proyecto_id = proyecto.id
        AND aprobacion.tipo_aprobacion = 'proyecto'
        AND aprobacion.estado = 'pendiente'
  );

DROP TABLE IF EXISTS cpos.documentos_proceso_aprobacion;
DROP TABLE IF EXISTS cpos.pasos_aprobacion;
DROP TABLE IF EXISTS cpos.procesos_aprobacion;

DELETE FROM cpos.rol_permiso
WHERE permiso_id IN (
    SELECT id FROM cpos.permisos
    WHERE codigo IN (
        'APROBACION_FORMAL_VER',
        'APROBACION_COORDINACION',
        'APROBACION_SUPERVISION',
        'PROYECTO_RESOLUCION_REGISTRAR'
    )
);

DELETE FROM cpos.permisos
WHERE codigo IN (
    'APROBACION_FORMAL_VER',
    'APROBACION_COORDINACION',
    'APROBACION_SUPERVISION',
    'PROYECTO_RESOLUCION_REGISTRAR'
);

INSERT INTO cpos.rol_permiso (rol_id, permiso_id)
SELECT rol.id, permiso.id
FROM cpos.roles rol
JOIN cpos.permisos permiso ON (
    (rol.nombre = 'coordinador' AND permiso.codigo = 'PROYECTO_APROBAR')
    OR
    (rol.nombre = 'supervisor' AND permiso.codigo IN (
        'ARCHIVO_SUBIR', 'ARTICULO_EDITAR', 'ASIGNACION_TUTOR_CAMBIAR',
        'ASIGNACION_TUTOR_CREAR', 'ASISTENCIA_REGISTRAR', 'CAMBIO_TEMA_SOLICITAR',
        'EVIDENCIA_EDITAR', 'EVIDENCIA_OBSERVAR', 'EVIDENCIA_SUBIR',
        'EVIDENCIA_VALIDAR', 'GRABACION_REGISTRAR', 'PROYECTO_CREAR',
        'PROYECTO_EDITAR', 'REPROGRAMACION_GESTIONAR', 'REPROGRAMACION_SOLICITAR',
        'TUTOR_CREAR', 'TUTOR_EDITAR', 'TUTORIA_EDITAR', 'TUTORIA_PROGRAMAR',
        'USUARIO_CREAR', 'USUARIO_DESACTIVAR', 'USUARIO_EDITAR'
    ))
)
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

COMMIT;
