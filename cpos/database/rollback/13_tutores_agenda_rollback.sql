/* Reversión de la Fase 5: tutores y agenda. */

BEGIN;

DROP INDEX IF EXISTS cpos.uq_reprogramacion_pendiente_tutoria;
DROP INDEX IF EXISTS cpos.uq_asignacion_tutor_activa_proyecto;
DROP INDEX IF EXISTS cpos.uq_cambio_tutor_pendiente_proyecto;

ALTER TABLE IF EXISTS cpos.tutorias
    DROP CONSTRAINT IF EXISTS ck_tutorias_numero_ocho,
    DROP CONSTRAINT IF EXISTS ck_tutorias_horario,
    DROP CONSTRAINT IF EXISTS ck_tutorias_enlace_https;

ALTER TABLE IF EXISTS cpos.reprogramaciones_tutoria
    DROP CONSTRAINT IF EXISTS ck_reprogramacion_horario,
    DROP COLUMN IF EXISTS observaciones_resolucion;

DELETE FROM cpos.aprobaciones
WHERE tipo_aprobacion = 'cambio_tutor'
  AND referencia_tabla = 'solicitudes_cambio_tutor';

DROP TABLE IF EXISTS cpos.solicitudes_cambio_tutor;
DROP TABLE IF EXISTS cpos.disponibilidades_tutor;
DROP TABLE IF EXISTS cpos.tutores_programas;

DELETE FROM cpos.rol_permiso rp
USING cpos.permisos permiso
WHERE rp.permiso_id = permiso.id
  AND permiso.codigo IN (
      'TUTOR_DISPONIBILIDAD_GESTIONAR',
      'CAMBIO_TUTOR_SOLICITAR',
      'CAMBIO_TUTOR_GESTIONAR',
      'CALENDARIO_TUTORIAS_VER'
  );

DELETE FROM cpos.permisos
WHERE codigo IN (
    'TUTOR_DISPONIBILIDAD_GESTIONAR',
    'CAMBIO_TUTOR_SOLICITAR',
    'CAMBIO_TUTOR_GESTIONAR',
    'CALENDARIO_TUTORIAS_VER'
);

COMMIT;
