/*
CPOS - FASE 7
Onboarding obligatorio del maestrante, modalidades configurables por el
supervisor, entregas por etapas con inmutabilidad tras aprobación, novena
tutoría excepcional autorizada y examen complexivo independiente.
Script idempotente para PostgreSQL/Supabase (usa IF NOT EXISTS / DO $$ guards).
NO se aplica automáticamente contra la base real: queda listo como archivo
para revisión y aplicación manual por un humano.
*/

BEGIN;

-- ---------------------------------------------------------------------
-- 7A. Onboarding obligatorio
-- ---------------------------------------------------------------------

ALTER TABLE cpos.maestrantes
    ADD COLUMN IF NOT EXISTS modulo_actual smallint NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS cpos.onboarding_maestrantes (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    maestrante_id bigint NOT NULL,
    estado varchar(30) NOT NULL DEFAULT 'pendiente',
    modalidad_seleccionada varchar(40) NULL,
    fecha_seleccion timestamptz NULL,
    seleccionado_por_id bigint NULL,
    observaciones text NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_onboarding_proyecto FOREIGN KEY (proyecto_id)
        REFERENCES cpos.proyectos_titulacion(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_onboarding_maestrante FOREIGN KEY (maestrante_id)
        REFERENCES cpos.maestrantes(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_onboarding_seleccionado_por FOREIGN KEY (seleccionado_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_onboarding_maestrante UNIQUE (maestrante_id),
    CONSTRAINT uq_onboarding_proyecto UNIQUE (proyecto_id),
    CONSTRAINT ck_onboarding_estado CHECK (
        estado IN ('pendiente', 'en_seleccion', 'completado', 'bloqueado', 'requiere_correccion')
    )
);

-- ---------------------------------------------------------------------
-- 7B. Modalidades configurables por el supervisor
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cpos.modalidades_configuradas (
    id bigserial PRIMARY KEY,
    programa_id bigint NULL,
    tipo_modalidad varchar(40) NOT NULL,
    nombre varchar(150) NOT NULL,
    descripcion text NULL,
    requiere_tutor boolean NOT NULL DEFAULT true,
    esta_activa boolean NOT NULL DEFAULT true,
    es_semilla_base boolean NOT NULL DEFAULT false,
    creado_por_id bigint NULL,
    actualizado_por_id bigint NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_modalidad_configurada_programa FOREIGN KEY (programa_id)
        REFERENCES cpos.programas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_modalidad_configurada_creado_por FOREIGN KEY (creado_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_modalidad_configurada_actualizado_por FOREIGN KEY (actualizado_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_modalidad_configurada_tipo CHECK (
        tipo_modalidad IN ('articulo_cientifico', 'proyecto_investigacion', 'examen_complexivo', 'otra')
    )
);

CREATE TABLE IF NOT EXISTS cpos.etapas_producto (
    id bigserial PRIMARY KEY,
    modalidad_id bigint NOT NULL,
    orden smallint NOT NULL,
    codigo varchar(60) NOT NULL,
    nombre varchar(150) NOT NULL,
    descripcion text NULL,
    es_obligatoria boolean NOT NULL DEFAULT true,
    esta_activa boolean NOT NULL DEFAULT true,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_etapa_producto_modalidad FOREIGN KEY (modalidad_id)
        REFERENCES cpos.modalidades_configuradas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_etapa_producto_modalidad_orden UNIQUE (modalidad_id, orden),
    CONSTRAINT uq_etapa_producto_modalidad_codigo UNIQUE (modalidad_id, codigo)
);

CREATE TABLE IF NOT EXISTS cpos.entregas_etapa (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    etapa_id bigint NOT NULL,
    numero_version integer NOT NULL DEFAULT 1,
    archivo_id bigint NULL,
    comentario_maestrante text NULL,
    estado varchar(30) NOT NULL DEFAULT 'borrador',
    evaluacion text NULL,
    observaciones text NULL,
    coordinador_responsable_id bigint NULL,
    fecha_evaluacion timestamptz NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_entrega_etapa_proyecto FOREIGN KEY (proyecto_id)
        REFERENCES cpos.proyectos_titulacion(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_entrega_etapa_etapa FOREIGN KEY (etapa_id)
        REFERENCES cpos.etapas_producto(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_entrega_etapa_archivo FOREIGN KEY (archivo_id)
        REFERENCES cpos.archivos_proyecto(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_entrega_etapa_coordinador FOREIGN KEY (coordinador_responsable_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_entrega_etapa_proyecto_etapa_version UNIQUE (proyecto_id, etapa_id, numero_version),
    CONSTRAINT ck_entrega_etapa_estado CHECK (
        estado IN ('borrador', 'enviada', 'en_revision', 'observada', 'aprobada', 'rechazada')
    ),
    CONSTRAINT ck_entrega_etapa_version CHECK (numero_version >= 1)
);

-- Inmutabilidad tras aprobación (mismo patrón que evidencia_versiones en Fase 6)
CREATE OR REPLACE FUNCTION cpos.fase7_proteger_entrega_aprobada()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Las entregas de etapa no pueden eliminarse.';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.estado = 'aprobada' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Una entrega de etapa aprobada es inmutable.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase7_entrega_aprobada ON cpos.entregas_etapa;
CREATE TRIGGER trg_fase7_entrega_aprobada
BEFORE UPDATE OR DELETE ON cpos.entregas_etapa
FOR EACH ROW EXECUTE FUNCTION cpos.fase7_proteger_entrega_aprobada();

-- Bloquea entregar una etapa obligatoria si la etapa obligatoria anterior
-- (mismo orden previo, misma modalidad) aún no tiene una entrega aprobada.
CREATE OR REPLACE FUNCTION cpos.fase7_validar_orden_etapas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    etapa_actual RECORD;
    etapa_previa_pendiente boolean;
BEGIN
    SELECT orden, modalidad_id, es_obligatoria
    INTO etapa_actual
    FROM cpos.etapas_producto
    WHERE id = NEW.etapa_id;

    IF etapa_actual.es_obligatoria THEN
        SELECT EXISTS (
            SELECT 1
            FROM cpos.etapas_producto previa
            WHERE previa.modalidad_id = etapa_actual.modalidad_id
              AND previa.es_obligatoria
              AND previa.orden < etapa_actual.orden
              AND NOT EXISTS (
                  SELECT 1 FROM cpos.entregas_etapa entrega
                  WHERE entrega.proyecto_id = NEW.proyecto_id
                    AND entrega.etapa_id = previa.id
                    AND entrega.estado = 'aprobada'
              )
        ) INTO etapa_previa_pendiente;

        IF etapa_previa_pendiente THEN
            RAISE EXCEPTION
                'No puede registrarse una entrega para esta etapa mientras existan etapas obligatorias previas sin aprobar.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase7_orden_etapas ON cpos.entregas_etapa;
CREATE TRIGGER trg_fase7_orden_etapas
BEFORE INSERT ON cpos.entregas_etapa
FOR EACH ROW EXECUTE FUNCTION cpos.fase7_validar_orden_etapas();

-- ---------------------------------------------------------------------
-- 7C. Novena tutoría excepcional
-- ---------------------------------------------------------------------

ALTER TABLE cpos.tutorias
    ADD COLUMN IF NOT EXISTS es_excepcional boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS cpos.autorizaciones_novena_tutoria (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    tutoria_id bigint NULL,
    solicitante_id bigint NULL,
    motivo text NOT NULL,
    autorizado_por_id bigint NULL,
    fecha_autorizacion timestamptz NOT NULL DEFAULT now(),
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_novena_proyecto FOREIGN KEY (proyecto_id)
        REFERENCES cpos.proyectos_titulacion(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_novena_tutoria FOREIGN KEY (tutoria_id)
        REFERENCES cpos.tutorias(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_novena_solicitante FOREIGN KEY (solicitante_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_novena_autorizado_por FOREIGN KEY (autorizado_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_novena_motivo CHECK (btrim(motivo) <> ''),
    CONSTRAINT uq_novena_tutoria UNIQUE (tutoria_id)
);

-- Amplía el rango permitido de numero_tutoria de 1-8 a 1-9. El CHECK simple no
-- puede validar "solo si existe autorización" (requiere subquery), así que esa
-- regla se aplica con un trigger BEFORE INSERT/UPDATE.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.tutorias'::regclass
          AND conname = 'ck_tutorias_numero_ocho'
    ) THEN
        ALTER TABLE cpos.tutorias DROP CONSTRAINT ck_tutorias_numero_ocho;
    END IF;
    ALTER TABLE cpos.tutorias
        ADD CONSTRAINT ck_tutorias_numero_nueve
        CHECK (numero_tutoria BETWEEN 1 AND 9);
END $$;

CREATE OR REPLACE FUNCTION cpos.fase7_validar_novena_tutoria()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    tiene_autorizacion boolean;
BEGIN
    IF NEW.numero_tutoria = 9 THEN
        SELECT EXISTS (
            SELECT 1 FROM cpos.autorizaciones_novena_tutoria autorizacion
            WHERE autorizacion.proyecto_id = NEW.proyecto_id
              AND (autorizacion.tutoria_id IS NULL OR autorizacion.tutoria_id = NEW.id)
        ) INTO tiene_autorizacion;

        IF NOT tiene_autorizacion THEN
            RAISE EXCEPTION
                'La novena tutoría requiere una autorización registrada previamente para el proyecto.';
        END IF;
        NEW.es_excepcional := true;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fase7_novena_tutoria ON cpos.tutorias;
CREATE TRIGGER trg_fase7_novena_tutoria
BEFORE INSERT OR UPDATE ON cpos.tutorias
FOR EACH ROW EXECUTE FUNCTION cpos.fase7_validar_novena_tutoria();

-- ---------------------------------------------------------------------
-- 7D. Examen complexivo (flujo independiente) y escala configurable
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cpos.escalas_calificacion (
    id bigserial PRIMARY KEY,
    programa_id bigint NULL,
    modalidad_id bigint NULL,
    nombre varchar(100) NOT NULL,
    nota_minima numeric(5,2) NOT NULL,
    nota_maxima numeric(5,2) NOT NULL,
    nota_aprobacion numeric(5,2) NOT NULL,
    esta_activa boolean NOT NULL DEFAULT true,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_escala_programa FOREIGN KEY (programa_id)
        REFERENCES cpos.programas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_escala_modalidad FOREIGN KEY (modalidad_id)
        REFERENCES cpos.modalidades_configuradas(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT ck_escala_rango CHECK (nota_maxima > nota_minima),
    CONSTRAINT ck_escala_aprobacion CHECK (
        nota_aprobacion BETWEEN nota_minima AND nota_maxima
    )
);

CREATE TABLE IF NOT EXISTS cpos.examenes_complexivos (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    escala_id bigint NULL,
    convocatoria varchar(150) NOT NULL,
    fecha_hora timestamptz NULL,
    tribunal text NULL,
    numero_intento smallint NOT NULL DEFAULT 1,
    calificacion numeric(5,2) NULL,
    resultado varchar(20) NOT NULL DEFAULT 'pendiente',
    observaciones text NULL,
    acta_url text NULL,
    fue_reprogramado boolean NOT NULL DEFAULT false,
    registrado_por_id bigint NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_examen_proyecto FOREIGN KEY (proyecto_id)
        REFERENCES cpos.proyectos_titulacion(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_examen_escala FOREIGN KEY (escala_id)
        REFERENCES cpos.escalas_calificacion(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_examen_registrado_por FOREIGN KEY (registrado_por_id)
        REFERENCES cpos.usuarios(id) ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_examen_proyecto_intento UNIQUE (proyecto_id, numero_intento),
    CONSTRAINT ck_examen_resultado CHECK (
        resultado IN ('pendiente', 'aprobado', 'reprobado', 'no_se_presento')
    ),
    CONSTRAINT ck_examen_intento CHECK (numero_intento >= 1)
);

-- ---------------------------------------------------------------------
-- Siembra de datos: migra REGLAS_BASE (apps/titulacion/modalidades.py) a la
-- tabla editable modalidades_configuradas + sus etapas_producto. Idempotente:
-- solo inserta si aún no existe una modalidad semilla del mismo tipo global.
-- ---------------------------------------------------------------------

DO $$
DECLARE
    id_articulo bigint;
    id_investigacion bigint;
    id_examen bigint;
BEGIN
    INSERT INTO cpos.modalidades_configuradas
        (programa_id, tipo_modalidad, nombre, descripcion, requiere_tutor, esta_activa, es_semilla_base)
    SELECT NULL, 'articulo_cientifico', 'Artículo científico',
           'Desarrollo de un artículo por secciones con etapas acumulativas.',
           true, true, true
    WHERE NOT EXISTS (
        SELECT 1 FROM cpos.modalidades_configuradas
        WHERE tipo_modalidad = 'articulo_cientifico' AND programa_id IS NULL AND es_semilla_base
    )
    RETURNING id INTO id_articulo;

    IF id_articulo IS NULL THEN
        SELECT id INTO id_articulo FROM cpos.modalidades_configuradas
        WHERE tipo_modalidad = 'articulo_cientifico' AND programa_id IS NULL AND es_semilla_base;
    END IF;

    INSERT INTO cpos.etapas_producto (modalidad_id, orden, codigo, nombre, es_obligatoria)
    SELECT id_articulo, etapa.orden, etapa.codigo, etapa.nombre, etapa.obligatoria
    FROM (VALUES
        (1, 'titulo_estructura', 'Título y estructura', true),
        (2, 'introduccion', 'Introducción', true),
        (3, 'metodologia', 'Metodología', true),
        (4, 'resultados', 'Resultados', true),
        (5, 'discusion', 'Discusión', false),
        (6, 'conclusiones', 'Conclusiones', true),
        (7, 'referencias', 'Referencias', true),
        (8, 'documento_final', 'Documento final consolidado', true)
    ) AS etapa(orden, codigo, nombre, obligatoria)
    WHERE NOT EXISTS (
        SELECT 1 FROM cpos.etapas_producto WHERE modalidad_id = id_articulo AND codigo = etapa.codigo
    );

    INSERT INTO cpos.modalidades_configuradas
        (programa_id, tipo_modalidad, nombre, descripcion, requiere_tutor, esta_activa, es_semilla_base)
    SELECT NULL, 'proyecto_investigacion', 'Proyecto de investigación',
           'Trabajo de investigación con documento final por etapas.',
           true, true, true
    WHERE NOT EXISTS (
        SELECT 1 FROM cpos.modalidades_configuradas
        WHERE tipo_modalidad = 'proyecto_investigacion' AND programa_id IS NULL AND es_semilla_base
    )
    RETURNING id INTO id_investigacion;

    IF id_investigacion IS NULL THEN
        SELECT id INTO id_investigacion FROM cpos.modalidades_configuradas
        WHERE tipo_modalidad = 'proyecto_investigacion' AND programa_id IS NULL AND es_semilla_base;
    END IF;

    INSERT INTO cpos.etapas_producto (modalidad_id, orden, codigo, nombre, es_obligatoria)
    SELECT id_investigacion, etapa.orden, etapa.codigo, etapa.nombre, etapa.obligatoria
    FROM (VALUES
        (1, 'planteamiento_problema', 'Planteamiento del problema', true),
        (2, 'objetivos', 'Objetivos', true),
        (3, 'marco_teorico', 'Marco teórico', true),
        (4, 'metodologia', 'Metodología', true),
        (5, 'resultados_propuesta', 'Resultados o propuesta', true),
        (6, 'conclusiones', 'Conclusiones', true),
        (7, 'recomendaciones', 'Recomendaciones', true),
        (8, 'bibliografia', 'Bibliografía', true),
        (9, 'anexos', 'Anexos', false),
        (10, 'documento_final', 'Documento final', true)
    ) AS etapa(orden, codigo, nombre, obligatoria)
    WHERE NOT EXISTS (
        SELECT 1 FROM cpos.etapas_producto WHERE modalidad_id = id_investigacion AND codigo = etapa.codigo
    );

    -- Examen complexivo NO usa etapas_producto (flujo independiente vía
    -- examenes_complexivos), pero se registra como modalidad configurada
    -- para que 7A/7B lo listen y el supervisor pueda desactivarlo.
    INSERT INTO cpos.modalidades_configuradas
        (programa_id, tipo_modalidad, nombre, descripcion, requiere_tutor, esta_activa, es_semilla_base)
    SELECT NULL, 'examen_complexivo', 'Examen complexivo',
           'Preparación, rendición y registro documental del resultado del examen.',
           false, true, true
    WHERE NOT EXISTS (
        SELECT 1 FROM cpos.modalidades_configuradas
        WHERE tipo_modalidad = 'examen_complexivo' AND programa_id IS NULL AND es_semilla_base
    )
    RETURNING id INTO id_examen;
END $$;

-- ---------------------------------------------------------------------
-- Permisos nuevos (patrón idéntico al usado en los SQL 11/13/14)
-- ---------------------------------------------------------------------

INSERT INTO cpos.permisos (
    codigo, nombre, modulo, descripcion, esta_activo, fecha_actualizacion
)
VALUES
    ('ONBOARDING_GESTIONAR', 'Gestionar onboarding propio', 'titulacion', 'Iniciar y completar el onboarding obligatorio del maestrante.', true, now()),
    ('ONBOARDING_CONSULTAR', 'Consultar onboarding', 'titulacion', 'Consultar el estado de onboarding de los maestrantes del programa.', true, now()),
    ('MODALIDAD_ETAPAS_CONFIGURAR', 'Configurar etapas de modalidad', 'titulacion', 'Crear/editar/activar/desactivar modalidades configuradas y sus etapas.', true, now()),
    ('MODALIDAD_ETAPAS_CONSULTAR', 'Consultar etapas de modalidad', 'titulacion', 'Consultar modalidades activas y sus etapas.', true, now()),
    ('ENTREGA_ETAPA_SUBIR', 'Subir entrega de etapa', 'seguimiento', 'Cargar una nueva versión de entrega para una etapa del producto final.', true, now()),
    ('ENTREGA_ETAPA_EVALUAR', 'Evaluar entrega de etapa', 'seguimiento', 'Aprobar, observar o rechazar una entrega de etapa.', true, now()),
    ('ENTREGA_ETAPA_CONSULTAR', 'Consultar entregas de etapa', 'seguimiento', 'Consultar entregas por etapa según el alcance del rol.', true, now()),
    ('TUTOR_ASIGNAR', 'Asignar tutor', 'titulacion', 'Asignar un tutor a un proyecto de titulación.', true, now()),
    ('NOVENA_TUTORIA_AUTORIZAR', 'Autorizar novena tutoría', 'titulacion', 'Autorizar excepcionalmente una novena sesión de tutoría.', true, now()),
    ('EXAMEN_COMPLEXIVO_GESTIONAR', 'Gestionar examen complexivo', 'titulacion', 'Registrar convocatoria, tribunal, resultado y reprogramaciones del examen complexivo.', true, now()),
    ('EXAMEN_COMPLEXIVO_CONSULTAR', 'Consultar examen complexivo', 'titulacion', 'Consultar el expediente del examen complexivo.', true, now()),
    ('ESCALA_CALIFICACION_CONFIGURAR', 'Configurar escala de calificación', 'titulacion', 'Definir la escala numérica de calificación por programa o modalidad.', true, now())
ON CONFLICT (codigo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    modulo = EXCLUDED.modulo,
    descripcion = EXCLUDED.descripcion,
    esta_activo = true,
    fecha_actualizacion = now();

-- Extiende MODALIDAD_CONFIGURAR (ya existente desde 11_modalidades_proyecto.sql)
-- al rol supervisor, sin quitarlo a coordinador/administrador_desarrollador.
INSERT INTO cpos.rol_permiso (rol_id, permiso_id)
SELECT rol.id, permiso.id
FROM cpos.roles rol
JOIN cpos.permisos permiso ON permiso.codigo = 'MODALIDAD_CONFIGURAR'
WHERE rol.nombre = 'supervisor'
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

INSERT INTO cpos.rol_permiso (rol_id, permiso_id)
SELECT rol.id, permiso.id
FROM cpos.roles rol
JOIN cpos.permisos permiso ON (
    (permiso.codigo = 'ONBOARDING_GESTIONAR' AND rol.nombre = 'maestrante')
    OR (permiso.codigo = 'ONBOARDING_CONSULTAR' AND rol.nombre IN ('coordinador', 'supervisor', 'administrador_desarrollador'))
    OR (permiso.codigo = 'MODALIDAD_ETAPAS_CONFIGURAR' AND rol.nombre IN ('supervisor', 'administrador_desarrollador'))
    OR (permiso.codigo = 'MODALIDAD_ETAPAS_CONSULTAR' AND rol.nombre IN ('maestrante', 'tutor', 'coordinador', 'supervisor', 'administrador_desarrollador'))
    OR (permiso.codigo = 'ENTREGA_ETAPA_SUBIR' AND rol.nombre = 'maestrante')
    OR (permiso.codigo = 'ENTREGA_ETAPA_EVALUAR' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'ENTREGA_ETAPA_CONSULTAR' AND rol.nombre IN ('maestrante', 'tutor', 'coordinador', 'supervisor'))
    OR (permiso.codigo = 'TUTOR_ASIGNAR' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'NOVENA_TUTORIA_AUTORIZAR' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'EXAMEN_COMPLEXIVO_GESTIONAR' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'EXAMEN_COMPLEXIVO_CONSULTAR' AND rol.nombre IN ('maestrante', 'tutor', 'coordinador', 'supervisor'))
    OR (permiso.codigo = 'ESCALA_CALIFICACION_CONFIGURAR' AND rol.nombre IN ('supervisor', 'coordinador', 'administrador_desarrollador'))
)
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

COMMIT;

SELECT
    (SELECT count(*) FROM cpos.modalidades_configuradas WHERE es_semilla_base) AS modalidades_semilla,
    (SELECT count(*) FROM cpos.etapas_producto) AS etapas_totales,
    (SELECT count(*) FROM cpos.onboarding_maestrantes) AS onboardings,
    (SELECT count(*) FROM cpos.entregas_etapa) AS entregas_etapa,
    (SELECT count(*) FROM cpos.autorizaciones_novena_tutoria) AS novenas_autorizadas,
    (SELECT count(*) FROM cpos.examenes_complexivos) AS examenes_complexivos;
