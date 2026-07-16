/*
CPOS - FASE 6
Asistencia auditada, estados coherentes, grabaciones versionadas y
evidencias vinculadas uno a uno con cada tutoría realizada.
Script idempotente para PostgreSQL/Supabase.
*/

BEGIN;

CREATE TABLE IF NOT EXISTS cpos.asistencias_tutoria_historial (
    id bigserial PRIMARY KEY,
    asistencia_id bigint NOT NULL,
    tutoria_id bigint NOT NULL,
    asistio_tutor_anterior boolean NOT NULL,
    asistio_maestrante_anterior boolean NOT NULL,
    estado_tutoria_anterior varchar(30) NOT NULL,
    asistio_tutor_nuevo boolean NOT NULL,
    asistio_maestrante_nuevo boolean NOT NULL,
    estado_tutoria_nuevo varchar(30) NOT NULL,
    observaciones_anteriores text NULL,
    observaciones_nuevas text NULL,
    motivo_correccion text NOT NULL,
    corregido_por_id bigint NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_asistencia_historial_asistencia FOREIGN KEY (asistencia_id)
        REFERENCES cpos.asistencias_tutoria(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_asistencia_historial_tutoria FOREIGN KEY (tutoria_id)
        REFERENCES cpos.tutorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_asistencia_historial_usuario FOREIGN KEY (corregido_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_asistencia_historial_motivo
        CHECK (btrim(motivo_correccion) <> ''),
    CONSTRAINT ck_asistencia_historial_estado_anterior CHECK (
        estado_tutoria_anterior IN (
            'programada', 'realizada', 'no_realizada', 'reprogramada', 'cancelada'
        )
    ),
    CONSTRAINT ck_asistencia_historial_estado_nuevo CHECK (
        estado_tutoria_nuevo IN (
            'programada', 'realizada', 'no_realizada', 'reprogramada', 'cancelada'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_asistencia_historial_tutoria
    ON cpos.asistencias_tutoria_historial (tutoria_id, fecha_creacion DESC);
CREATE INDEX IF NOT EXISTS idx_asistencia_historial_usuario
    ON cpos.asistencias_tutoria_historial (corregido_por_id, fecha_creacion DESC);

ALTER TABLE cpos.grabaciones
    ADD COLUMN IF NOT EXISTS numero_version integer,
    ADD COLUMN IF NOT EXISTS esta_activa boolean,
    ADD COLUMN IF NOT EXISTS reemplaza_grabacion_id bigint NULL,
    ADD COLUMN IF NOT EXISTS fecha_actualizacion timestamptz;

WITH ordenadas AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY tutoria_id ORDER BY fecha_creacion, id
           )::integer AS numero,
           row_number() OVER (
               PARTITION BY tutoria_id ORDER BY fecha_creacion DESC, id DESC
           ) = 1 AS activa
    FROM cpos.grabaciones
)
UPDATE cpos.grabaciones grabacion
SET numero_version = COALESCE(grabacion.numero_version, ordenadas.numero),
    esta_activa = COALESCE(grabacion.esta_activa, ordenadas.activa),
    fecha_actualizacion = COALESCE(
        grabacion.fecha_actualizacion,
        grabacion.fecha_creacion,
        now()
    )
FROM ordenadas
WHERE ordenadas.id = grabacion.id
  AND (
      grabacion.numero_version IS NULL
      OR grabacion.esta_activa IS NULL
      OR grabacion.fecha_actualizacion IS NULL
  );

ALTER TABLE cpos.grabaciones
    ALTER COLUMN numero_version SET DEFAULT 1,
    ALTER COLUMN numero_version SET NOT NULL,
    ALTER COLUMN esta_activa SET DEFAULT true,
    ALTER COLUMN esta_activa SET NOT NULL,
    ALTER COLUMN fecha_actualizacion SET DEFAULT now(),
    ALTER COLUMN fecha_actualizacion SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.grabaciones'::regclass
          AND conname = 'fk_grabacion_reemplazada'
    ) THEN
        ALTER TABLE cpos.grabaciones
            ADD CONSTRAINT fk_grabacion_reemplazada
            FOREIGN KEY (reemplaza_grabacion_id)
            REFERENCES cpos.grabaciones(id)
            ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.grabaciones'::regclass
          AND conname = 'ck_grabacion_numero_version'
    ) THEN
        ALTER TABLE cpos.grabaciones
            ADD CONSTRAINT ck_grabacion_numero_version
            CHECK (numero_version >= 1);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.grabaciones'::regclass
          AND conname = 'ck_grabacion_enlace_https'
    ) THEN
        ALTER TABLE cpos.grabaciones
            ADD CONSTRAINT ck_grabacion_enlace_https CHECK (
                tipo_grabacion <> 'enlace'
                OR enlace_grabacion ~* '^https://'
            );
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_grabacion_tutoria_version
    ON cpos.grabaciones (tutoria_id, numero_version);
CREATE UNIQUE INDEX IF NOT EXISTS uq_grabacion_activa_tutoria
    ON cpos.grabaciones (tutoria_id)
    WHERE esta_activa;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM cpos.evidencias
        GROUP BY tutoria_id HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'No se puede aplicar Fase 6: existen tutorías con más de una evidencia.';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_evidencia_principal_tutoria
    ON cpos.evidencias (tutoria_id);

ALTER TABLE cpos.evidencias
    DROP CONSTRAINT IF EXISTS ck_evidencias_estado;
ALTER TABLE cpos.evidencias
    ADD CONSTRAINT ck_evidencias_estado CHECK (
        estado IN (
            'pendiente', 'cargada', 'en_revision',
            'observada', 'validada', 'rechazada'
        )
    );

ALTER TABLE cpos.evidencia_versiones
    ADD COLUMN IF NOT EXISTS estado varchar(30),
    ADD COLUMN IF NOT EXISTS fecha_actualizacion timestamptz;

UPDATE cpos.evidencia_versiones version
SET estado = COALESCE(
        version.estado,
        CASE
            WHEN version.numero_version = evidencia.version_actual
                THEN evidencia.estado
            ELSE 'observada'
        END
    ),
    fecha_actualizacion = COALESCE(
        version.fecha_actualizacion,
        version.fecha_creacion,
        now()
    )
FROM cpos.evidencias evidencia
WHERE evidencia.id = version.evidencia_id
  AND (version.estado IS NULL OR version.fecha_actualizacion IS NULL);

ALTER TABLE cpos.evidencia_versiones
    ALTER COLUMN estado SET DEFAULT 'en_revision',
    ALTER COLUMN estado SET NOT NULL,
    ALTER COLUMN fecha_actualizacion SET DEFAULT now(),
    ALTER COLUMN fecha_actualizacion SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.evidencia_versiones'::regclass
          AND conname = 'ck_evidencia_version_estado'
    ) THEN
        ALTER TABLE cpos.evidencia_versiones
            ADD CONSTRAINT ck_evidencia_version_estado CHECK (
                estado IN (
                    'pendiente', 'cargada', 'en_revision',
                    'observada', 'validada', 'rechazada'
                )
            );
    END IF;
END $$;

ALTER TABLE cpos.validaciones_evidencia
    ADD COLUMN IF NOT EXISTS evidencia_version_id bigint NULL;

UPDATE cpos.validaciones_evidencia validacion
SET evidencia_version_id = version.id
FROM cpos.evidencias evidencia
JOIN cpos.evidencia_versiones version
  ON version.evidencia_id = evidencia.id
 AND version.numero_version = evidencia.version_actual
WHERE validacion.evidencia_id = evidencia.id
  AND validacion.evidencia_version_id IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM cpos.validaciones_evidencia
        WHERE evidencia_version_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'No se puede enlazar una validación con su versión de evidencia.';
    END IF;
END $$;

ALTER TABLE cpos.validaciones_evidencia
    ALTER COLUMN evidencia_version_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.validaciones_evidencia'::regclass
          AND conname = 'fk_validacion_evidencia_version'
    ) THEN
        ALTER TABLE cpos.validaciones_evidencia
            ADD CONSTRAINT fk_validacion_evidencia_version
            FOREIGN KEY (evidencia_version_id)
            REFERENCES cpos.evidencia_versiones(id)
            ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.validaciones_evidencia'::regclass
          AND conname = 'ck_validacion_motivo_obligatorio'
    ) THEN
        ALTER TABLE cpos.validaciones_evidencia
            ADD CONSTRAINT ck_validacion_motivo_obligatorio CHECK (
                estado_resultado = 'validada'
                OR btrim(observaciones) <> ''
            );
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_validacion_evidencia_version
    ON cpos.validaciones_evidencia (evidencia_version_id);

CREATE OR REPLACE FUNCTION cpos.fase6_validar_estado_tutoria()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    asistencia_completa boolean;
BEGIN
    IF NEW.estado IS NOT DISTINCT FROM OLD.estado THEN
        RETURN NEW;
    END IF;

    IF OLD.estado = 'cancelada' THEN
        RAISE EXCEPTION 'Una tutoría cancelada es un estado terminal.';
    END IF;
    IF OLD.estado = 'realizada' AND NEW.estado = 'reprogramada' THEN
        RAISE EXCEPTION 'Una tutoría realizada no puede reprogramarse.';
    END IF;
    IF NEW.estado = 'realizada' THEN
        IF (NEW.fecha + NEW.hora_fin) > CURRENT_TIMESTAMP THEN
            RAISE EXCEPTION 'Una tutoría futura no puede marcarse como realizada.';
        END IF;
        SELECT a.asistio_tutor AND a.asistio_maestrante
        INTO asistencia_completa
        FROM cpos.asistencias_tutoria a
        WHERE a.tutoria_id = NEW.id;
        IF COALESCE(asistencia_completa, false) IS NOT TRUE THEN
            RAISE EXCEPTION
                'La tutoría requiere asistencia del tutor y del maestrante.';
        END IF;
    END IF;
    IF NEW.estado IN ('no_realizada', 'cancelada') AND (
        EXISTS (SELECT 1 FROM cpos.evidencias e WHERE e.tutoria_id = NEW.id)
        OR EXISTS (
            SELECT 1 FROM cpos.grabaciones g
            WHERE g.tutoria_id = NEW.id AND g.esta_activa
        )
    ) THEN
        RAISE EXCEPTION
            'La tutoría tiene evidencia o grabación y no puede invalidarse.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_estado_tutoria ON cpos.tutorias;
CREATE TRIGGER trg_fase6_estado_tutoria
BEFORE UPDATE OF estado ON cpos.tutorias
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_estado_tutoria();

CREATE OR REPLACE FUNCTION cpos.fase6_validar_asistencia()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    estado_actual varchar(30);
BEGIN
    SELECT estado INTO estado_actual
    FROM cpos.tutorias WHERE id = NEW.tutoria_id;
    IF estado_actual = 'realizada'
       AND (NOT NEW.asistio_tutor OR NOT NEW.asistio_maestrante) THEN
        RAISE EXCEPTION
            'No se puede dejar incompleta la asistencia de una tutoría realizada.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_asistencia ON cpos.asistencias_tutoria;
CREATE TRIGGER trg_fase6_asistencia
BEFORE INSERT OR UPDATE ON cpos.asistencias_tutoria
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_asistencia();

CREATE OR REPLACE FUNCTION cpos.fase6_validar_producto_tutoria()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    sesion_valida boolean;
BEGIN
    SELECT t.estado = 'realizada'
           AND a.asistio_tutor
           AND a.asistio_maestrante
    INTO sesion_valida
    FROM cpos.tutorias t
    LEFT JOIN cpos.asistencias_tutoria a ON a.tutoria_id = t.id
    WHERE t.id = NEW.tutoria_id;
    IF COALESCE(sesion_valida, false) IS NOT TRUE THEN
        RAISE EXCEPTION
            'Solo una tutoría realizada con asistencia completa admite productos.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_evidencia_tutoria ON cpos.evidencias;
CREATE TRIGGER trg_fase6_evidencia_tutoria
BEFORE INSERT OR UPDATE OF tutoria_id ON cpos.evidencias
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_producto_tutoria();

DROP TRIGGER IF EXISTS trg_fase6_grabacion_tutoria ON cpos.grabaciones;
CREATE TRIGGER trg_fase6_grabacion_tutoria
BEFORE INSERT OR UPDATE OF tutoria_id ON cpos.grabaciones
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_producto_tutoria();

CREATE OR REPLACE FUNCTION cpos.fase6_validar_revision_evidencia()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    evidencia_version_padre bigint;
    tutor_asignado_usuario bigint;
BEGIN
    SELECT version.evidencia_id
    INTO evidencia_version_padre
    FROM cpos.evidencia_versiones version
    WHERE version.id = NEW.evidencia_version_id;
    IF evidencia_version_padre IS DISTINCT FROM NEW.evidencia_id THEN
        RAISE EXCEPTION
            'La validación no corresponde a la versión indicada.';
    END IF;

    SELECT tutor.usuario_id
    INTO tutor_asignado_usuario
    FROM cpos.evidencias evidencia
    JOIN cpos.tutorias tutoria ON tutoria.id = evidencia.tutoria_id
    JOIN cpos.tutores tutor ON tutor.id = tutoria.tutor_id
    WHERE evidencia.id = NEW.evidencia_id;
    IF NEW.validado_por_id IS DISTINCT FROM tutor_asignado_usuario THEN
        RAISE EXCEPTION
            'Solo el tutor asignado puede revisar la evidencia.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_revision_evidencia
    ON cpos.validaciones_evidencia;
CREATE TRIGGER trg_fase6_revision_evidencia
BEFORE INSERT OR UPDATE ON cpos.validaciones_evidencia
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_revision_evidencia();

CREATE OR REPLACE FUNCTION cpos.fase6_proteger_version_validada()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Las versiones de evidencia no pueden eliminarse.';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.estado = 'validada' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Una versión validada es inmutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_version_validada
    ON cpos.evidencia_versiones;
CREATE TRIGGER trg_fase6_version_validada
BEFORE UPDATE OR DELETE ON cpos.evidencia_versiones
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_proteger_version_validada();

CREATE OR REPLACE FUNCTION cpos.fase6_proteger_evidencia_resuelta()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Las evidencias no pueden eliminarse.';
    END IF;
    IF OLD.estado IN ('validada', 'rechazada') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Una evidencia resuelta es inmutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_evidencia_resuelta ON cpos.evidencias;
CREATE TRIGGER trg_fase6_evidencia_resuelta
BEFORE UPDATE OR DELETE ON cpos.evidencias
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_proteger_evidencia_resuelta();

CREATE OR REPLACE FUNCTION cpos.fase6_validar_autor_producto()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    usuario_esperado bigint;
BEGIN
    IF TG_TABLE_NAME = 'evidencias' THEN
        SELECT maestrante.usuario_id
        INTO usuario_esperado
        FROM cpos.proyectos_titulacion proyecto
        JOIN cpos.maestrantes maestrante ON maestrante.id = proyecto.maestrante_id
        WHERE proyecto.id = NEW.proyecto_id;
        IF NEW.subido_por_id IS DISTINCT FROM usuario_esperado THEN
            RAISE EXCEPTION
                'Solo el maestrante propietario puede cargar la evidencia.';
        END IF;
    ELSIF TG_TABLE_NAME = 'grabaciones' THEN
        SELECT tutor.usuario_id
        INTO usuario_esperado
        FROM cpos.tutorias tutoria
        JOIN cpos.tutores tutor ON tutor.id = tutoria.tutor_id
        WHERE tutoria.id = NEW.tutoria_id;
        IF NEW.registrado_por_id IS DISTINCT FROM usuario_esperado THEN
            RAISE EXCEPTION
                'Solo el tutor asignado puede registrar la grabación.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_autor_evidencia ON cpos.evidencias;
CREATE TRIGGER trg_fase6_autor_evidencia
BEFORE INSERT ON cpos.evidencias
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_autor_producto();

DROP TRIGGER IF EXISTS trg_fase6_autor_grabacion ON cpos.grabaciones;
CREATE TRIGGER trg_fase6_autor_grabacion
BEFORE INSERT ON cpos.grabaciones
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_validar_autor_producto();

CREATE OR REPLACE FUNCTION cpos.fase6_proteger_grabacion_historica()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Las versiones de grabación no pueden eliminarse.';
    END IF;
    IF NOT OLD.esta_activa AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Una grabación histórica es inmutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase6_grabacion_historica ON cpos.grabaciones;
CREATE TRIGGER trg_fase6_grabacion_historica
BEFORE UPDATE OR DELETE ON cpos.grabaciones
FOR EACH ROW EXECUTE FUNCTION cpos.fase6_proteger_grabacion_historica();

INSERT INTO cpos.permisos (
    codigo, nombre, modulo, descripcion, esta_activo, fecha_actualizacion
)
VALUES
    ('ASISTENCIA_CORREGIR', 'Corregir asistencia', 'seguimiento', 'Corregir justificadamente una asistencia dentro del programa.', true, now()),
    ('GRABACION_REEMPLAZAR', 'Reemplazar grabación', 'seguimiento', 'Crear una nueva versión sin borrar la grabación anterior.', true, now()),
    ('EVIDENCIA_RECHAZAR', 'Rechazar evidencia', 'seguimiento', 'Rechazar justificadamente la versión actual de una evidencia.', true, now()),
    ('SEGUIMIENTO_CONSULTAR', 'Consultar seguimiento', 'seguimiento', 'Consultar asistencia, grabaciones, evidencias y versiones según el alcance del rol.', true, now())
ON CONFLICT (codigo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    modulo = EXCLUDED.modulo,
    descripcion = EXCLUDED.descripcion,
    esta_activo = true,
    fecha_actualizacion = now();

INSERT INTO cpos.rol_permiso (rol_id, permiso_id)
SELECT rol.id, permiso.id
FROM cpos.roles rol
JOIN cpos.permisos permiso ON (
    (permiso.codigo = 'ASISTENCIA_CORREGIR' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'GRABACION_REEMPLAZAR' AND rol.nombre = 'tutor')
    OR (permiso.codigo = 'EVIDENCIA_RECHAZAR' AND rol.nombre = 'tutor')
    OR (
        permiso.codigo = 'SEGUIMIENTO_CONSULTAR'
        AND rol.nombre IN ('maestrante', 'tutor', 'coordinador', 'supervisor')
    )
)
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

COMMIT;

SELECT
    (SELECT count(*) FROM cpos.asistencias_tutoria_historial) AS correcciones_asistencia,
    (SELECT count(*) FROM cpos.grabaciones WHERE esta_activa) AS grabaciones_activas,
    (SELECT count(*) FROM cpos.evidencias) AS evidencias,
    (SELECT count(*) FROM cpos.validaciones_evidencia) AS validaciones;
