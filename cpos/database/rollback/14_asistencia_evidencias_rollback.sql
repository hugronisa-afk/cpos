/* Reversión segura de la Fase 6: asistencia, grabaciones y evidencias. */

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM cpos.asistencias_tutoria_historial) THEN
        RAISE EXCEPTION
            'Existen correcciones de asistencia. Expórtelas antes de revertir.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM cpos.grabaciones
        WHERE numero_version > 1 OR NOT esta_activa
    ) THEN
        RAISE EXCEPTION
            'Existen versiones históricas de grabaciones. No se pueden descartar.';
    END IF;
    IF EXISTS (SELECT 1 FROM cpos.evidencia_versiones) THEN
        RAISE EXCEPTION
            'Existen versiones de evidencias. No se puede perder su estado histórico.';
    END IF;
END $$;

DROP TRIGGER IF EXISTS trg_fase6_evidencia_tutoria ON cpos.evidencias;
DROP TRIGGER IF EXISTS trg_fase6_grabacion_tutoria ON cpos.grabaciones;
DROP TRIGGER IF EXISTS trg_fase6_revision_evidencia ON cpos.validaciones_evidencia;
DROP TRIGGER IF EXISTS trg_fase6_version_validada ON cpos.evidencia_versiones;
DROP TRIGGER IF EXISTS trg_fase6_evidencia_resuelta ON cpos.evidencias;
DROP TRIGGER IF EXISTS trg_fase6_autor_evidencia ON cpos.evidencias;
DROP TRIGGER IF EXISTS trg_fase6_autor_grabacion ON cpos.grabaciones;
DROP TRIGGER IF EXISTS trg_fase6_grabacion_historica ON cpos.grabaciones;
DROP TRIGGER IF EXISTS trg_fase6_asistencia ON cpos.asistencias_tutoria;
DROP TRIGGER IF EXISTS trg_fase6_estado_tutoria ON cpos.tutorias;
DROP FUNCTION IF EXISTS cpos.fase6_validar_producto_tutoria();
DROP FUNCTION IF EXISTS cpos.fase6_validar_revision_evidencia();
DROP FUNCTION IF EXISTS cpos.fase6_proteger_version_validada();
DROP FUNCTION IF EXISTS cpos.fase6_proteger_evidencia_resuelta();
DROP FUNCTION IF EXISTS cpos.fase6_validar_autor_producto();
DROP FUNCTION IF EXISTS cpos.fase6_proteger_grabacion_historica();
DROP FUNCTION IF EXISTS cpos.fase6_validar_asistencia();
DROP FUNCTION IF EXISTS cpos.fase6_validar_estado_tutoria();

DROP INDEX IF EXISTS cpos.uq_validacion_evidencia_version;
ALTER TABLE cpos.validaciones_evidencia
    DROP CONSTRAINT IF EXISTS fk_validacion_evidencia_version,
    DROP CONSTRAINT IF EXISTS ck_validacion_motivo_obligatorio,
    DROP COLUMN IF EXISTS evidencia_version_id;

ALTER TABLE cpos.evidencia_versiones
    DROP CONSTRAINT IF EXISTS ck_evidencia_version_estado,
    DROP COLUMN IF EXISTS estado,
    DROP COLUMN IF EXISTS fecha_actualizacion;

ALTER TABLE cpos.evidencias
    DROP CONSTRAINT IF EXISTS ck_evidencias_estado;
ALTER TABLE cpos.evidencias
    ADD CONSTRAINT ck_evidencias_estado CHECK (
        estado IN ('pendiente', 'en_revision', 'validada', 'observada', 'rechazada')
    );
DROP INDEX IF EXISTS cpos.uq_evidencia_principal_tutoria;

DROP INDEX IF EXISTS cpos.uq_grabacion_activa_tutoria;
DROP INDEX IF EXISTS cpos.uq_grabacion_tutoria_version;
ALTER TABLE cpos.grabaciones
    DROP CONSTRAINT IF EXISTS fk_grabacion_reemplazada,
    DROP CONSTRAINT IF EXISTS ck_grabacion_numero_version,
    DROP CONSTRAINT IF EXISTS ck_grabacion_enlace_https,
    DROP COLUMN IF EXISTS reemplaza_grabacion_id,
    DROP COLUMN IF EXISTS numero_version,
    DROP COLUMN IF EXISTS esta_activa,
    DROP COLUMN IF EXISTS fecha_actualizacion;

DROP TABLE IF EXISTS cpos.asistencias_tutoria_historial;

DELETE FROM cpos.rol_permiso rp
USING cpos.permisos permiso
WHERE rp.permiso_id = permiso.id
  AND permiso.codigo IN (
      'ASISTENCIA_CORREGIR', 'GRABACION_REEMPLAZAR',
      'EVIDENCIA_RECHAZAR', 'SEGUIMIENTO_CONSULTAR'
  );
DELETE FROM cpos.permisos
WHERE codigo IN (
    'ASISTENCIA_CORREGIR', 'GRABACION_REEMPLAZAR',
    'EVIDENCIA_RECHAZAR', 'SEGUIMIENTO_CONSULTAR'
);

COMMIT;
