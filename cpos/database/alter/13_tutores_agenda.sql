/*
CPOS - FASE 5
Tutores por programa, disponibilidad, cambios autorizados y agenda de ocho tutorías.
Script idempotente para PostgreSQL/Supabase.
*/

BEGIN;

CREATE TABLE IF NOT EXISTS cpos.tutores_programas (
    id bigserial PRIMARY KEY,
    tutor_id bigint NOT NULL,
    programa_id bigint NOT NULL,
    cupo_maximo smallint NOT NULL DEFAULT 5,
    esta_activo boolean NOT NULL DEFAULT true,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_tutores_programas_tutor_programa UNIQUE (tutor_id, programa_id),
    CONSTRAINT fk_tutores_programas_tutor FOREIGN KEY (tutor_id)
        REFERENCES cpos.tutores(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_tutores_programas_programa FOREIGN KEY (programa_id)
        REFERENCES cpos.programas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_tutores_programas_cupo CHECK (cupo_maximo BETWEEN 1 AND 50)
);

CREATE TABLE IF NOT EXISTS cpos.disponibilidades_tutor (
    id bigserial PRIMARY KEY,
    tutor_id bigint NOT NULL,
    dia_semana smallint NOT NULL,
    hora_inicio time NOT NULL,
    hora_fin time NOT NULL,
    esta_activa boolean NOT NULL DEFAULT true,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_disponibilidad_tutor_bloque
        UNIQUE (tutor_id, dia_semana, hora_inicio, hora_fin),
    CONSTRAINT fk_disponibilidad_tutor FOREIGN KEY (tutor_id)
        REFERENCES cpos.tutores(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_disponibilidad_dia CHECK (dia_semana BETWEEN 0 AND 6),
    CONSTRAINT ck_disponibilidad_horas CHECK (hora_fin > hora_inicio)
);

CREATE TABLE IF NOT EXISTS cpos.solicitudes_cambio_tutor (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    asignacion_actual_id bigint NOT NULL,
    tutor_propuesto_id bigint NOT NULL,
    motivo text NOT NULL,
    solicitado_por_id bigint NULL,
    estado varchar(20) NOT NULL DEFAULT 'pendiente',
    resuelto_por_id bigint NULL,
    observaciones_resolucion text NULL,
    fecha_resolucion timestamptz NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_cambio_tutor_proyecto FOREIGN KEY (proyecto_id)
        REFERENCES cpos.proyectos_titulacion(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cambio_tutor_asignacion FOREIGN KEY (asignacion_actual_id)
        REFERENCES cpos.asignaciones_tutor(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cambio_tutor_propuesto FOREIGN KEY (tutor_propuesto_id)
        REFERENCES cpos.tutores(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cambio_tutor_solicitado_por FOREIGN KEY (solicitado_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_cambio_tutor_resuelto_por FOREIGN KEY (resuelto_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_cambio_tutor_motivo CHECK (trim(motivo) <> ''),
    CONSTRAINT ck_cambio_tutor_estado CHECK (
        estado IN ('pendiente', 'aprobada', 'rechazada', 'cancelada')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cambio_tutor_pendiente_proyecto
    ON cpos.solicitudes_cambio_tutor (proyecto_id)
    WHERE estado = 'pendiente';

CREATE UNIQUE INDEX IF NOT EXISTS uq_asignacion_tutor_activa_proyecto
    ON cpos.asignaciones_tutor (proyecto_id)
    WHERE estado = 'activo';

CREATE UNIQUE INDEX IF NOT EXISTS uq_reprogramacion_pendiente_tutoria
    ON cpos.reprogramaciones_tutoria (tutoria_id)
    WHERE estado = 'pendiente';

ALTER TABLE cpos.reprogramaciones_tutoria
    ADD COLUMN IF NOT EXISTS observaciones_resolucion text NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.tutorias'::regclass
          AND conname = 'ck_tutorias_numero_ocho'
    ) THEN
        ALTER TABLE cpos.tutorias
            ADD CONSTRAINT ck_tutorias_numero_ocho
            CHECK (numero_tutoria BETWEEN 1 AND 8);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.tutorias'::regclass
          AND conname = 'ck_tutorias_horario'
    ) THEN
        ALTER TABLE cpos.tutorias
            ADD CONSTRAINT ck_tutorias_horario CHECK (hora_fin > hora_inicio);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.tutorias'::regclass
          AND conname = 'ck_tutorias_enlace_https'
    ) THEN
        ALTER TABLE cpos.tutorias
            ADD CONSTRAINT ck_tutorias_enlace_https
            CHECK (enlace_virtual IS NULL OR enlace_virtual ~* '^https://');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.reprogramaciones_tutoria'::regclass
          AND conname = 'ck_reprogramacion_horario'
    ) THEN
        ALTER TABLE cpos.reprogramaciones_tutoria
            ADD CONSTRAINT ck_reprogramacion_horario
            CHECK (hora_fin_nueva > hora_inicio_nueva);
    END IF;
END $$;

/* Adopta los programas y horarios que ya estaban demostrados por datos reales. */
INSERT INTO cpos.tutores_programas (tutor_id, programa_id)
SELECT DISTINCT asignacion.tutor_id, maestrante.programa_id
FROM cpos.asignaciones_tutor asignacion
JOIN cpos.proyectos_titulacion proyecto ON proyecto.id = asignacion.proyecto_id
JOIN cpos.maestrantes maestrante ON maestrante.id = proyecto.maestrante_id
ON CONFLICT (tutor_id, programa_id) DO UPDATE SET
    esta_activo = true,
    fecha_actualizacion = now();

INSERT INTO cpos.disponibilidades_tutor (
    tutor_id, dia_semana, hora_inicio, hora_fin
)
SELECT DISTINCT
    tutoria.tutor_id,
    EXTRACT(ISODOW FROM tutoria.fecha)::smallint - 1,
    tutoria.hora_inicio,
    tutoria.hora_fin
FROM cpos.tutorias tutoria
WHERE tutoria.hora_fin > tutoria.hora_inicio
ON CONFLICT (tutor_id, dia_semana, hora_inicio, hora_fin) DO UPDATE SET
    esta_activa = true,
    fecha_actualizacion = now();

INSERT INTO cpos.permisos (
    codigo, nombre, modulo, descripcion, esta_activo, fecha_actualizacion
)
VALUES
    ('TUTOR_DISPONIBILIDAD_GESTIONAR', 'Gestionar disponibilidad de tutor', 'titulacion', 'Registrar y activar horarios semanales de disponibilidad.', true, now()),
    ('CAMBIO_TUTOR_SOLICITAR', 'Solicitar cambio de tutor', 'titulacion', 'Solicitar justificadamente el reemplazo del tutor asignado.', true, now()),
    ('CAMBIO_TUTOR_GESTIONAR', 'Resolver cambio de tutor', 'titulacion', 'Aprobar o rechazar solicitudes de cambio dentro del programa.', true, now()),
    ('CALENDARIO_TUTORIAS_VER', 'Ver calendario de tutorías', 'titulacion', 'Consultar la agenda de tutorías según el alcance del rol.', true, now())
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
    (permiso.codigo = 'TUTOR_DISPONIBILIDAD_GESTIONAR' AND rol.nombre IN ('tutor', 'coordinador'))
    OR (permiso.codigo = 'CAMBIO_TUTOR_SOLICITAR' AND rol.nombre IN ('maestrante', 'tutor'))
    OR (permiso.codigo = 'CAMBIO_TUTOR_GESTIONAR' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'CALENDARIO_TUTORIAS_VER' AND rol.nombre IN ('maestrante', 'tutor', 'coordinador', 'supervisor'))
    OR (permiso.codigo = 'REPROGRAMACION_SOLICITAR' AND rol.nombre = 'maestrante')
)
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

COMMIT;

SELECT
    (SELECT count(*) FROM cpos.tutores_programas) AS vinculos_programa,
    (SELECT count(*) FROM cpos.disponibilidades_tutor) AS disponibilidades,
    (SELECT count(*) FROM cpos.solicitudes_cambio_tutor) AS cambios_tutor;
