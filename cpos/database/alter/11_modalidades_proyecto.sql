/*
CPOS - FASE 3
Motor de modalidades, configuración de «Otra» por programa y cambios formales.
Script idempotente para PostgreSQL/Supabase.
*/

BEGIN;

CREATE TABLE IF NOT EXISTS cpos.configuraciones_modalidad_programa (
    id bigserial PRIMARY KEY,
    programa_id bigint NOT NULL,
    nombre varchar(150) NOT NULL,
    descripcion text NOT NULL,
    tipos_evidencia jsonb NOT NULL DEFAULT '[]'::jsonb,
    producto_final_nombre varchar(150) NOT NULL,
    tipo_archivo_final varchar(30) NOT NULL DEFAULT 'pdf',
    esta_activa boolean NOT NULL DEFAULT true,
    creado_por_id bigint NULL,
    actualizado_por_id bigint NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_config_modalidad_programa UNIQUE (programa_id),
    CONSTRAINT fk_config_modalidad_programa_programa
        FOREIGN KEY (programa_id) REFERENCES cpos.programas(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_config_modalidad_programa_creado_por
        FOREIGN KEY (creado_por_id) REFERENCES cpos.usuarios(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_config_modalidad_programa_actualizado_por
        FOREIGN KEY (actualizado_por_id) REFERENCES cpos.usuarios(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_config_modalidad_nombre
        CHECK (trim(nombre) <> ''),
    CONSTRAINT ck_config_modalidad_descripcion
        CHECK (trim(descripcion) <> ''),
    CONSTRAINT ck_config_modalidad_evidencias
        CHECK (jsonb_typeof(tipos_evidencia) = 'array' AND jsonb_array_length(tipos_evidencia) > 0),
    CONSTRAINT ck_config_modalidad_producto
        CHECK (trim(producto_final_nombre) <> ''),
    CONSTRAINT ck_config_modalidad_tipo_archivo
        CHECK (tipo_archivo_final IN ('word', 'pdf', 'resolucion', 'anexo'))
);

CREATE TABLE IF NOT EXISTS cpos.solicitudes_cambio_modalidad (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    modalidad_actual varchar(40) NOT NULL,
    modalidad_propuesta varchar(40) NOT NULL,
    justificacion text NOT NULL,
    solicitado_por_id bigint NULL,
    estado varchar(30) NOT NULL DEFAULT 'pendiente',
    resuelto_por_id bigint NULL,
    observaciones_resolucion text NULL,
    fecha_resolucion timestamptz NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_cambio_modalidad_proyecto
        FOREIGN KEY (proyecto_id) REFERENCES cpos.proyectos_titulacion(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_cambio_modalidad_solicitado_por
        FOREIGN KEY (solicitado_por_id) REFERENCES cpos.usuarios(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_cambio_modalidad_resuelto_por
        FOREIGN KEY (resuelto_por_id) REFERENCES cpos.usuarios(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT ck_cambio_modalidad_actual
        CHECK (modalidad_actual IN ('articulo_cientifico', 'proyecto_investigacion', 'examen_complexivo', 'otra')),
    CONSTRAINT ck_cambio_modalidad_propuesta
        CHECK (modalidad_propuesta IN ('articulo_cientifico', 'proyecto_investigacion', 'examen_complexivo', 'otra')),
    CONSTRAINT ck_cambio_modalidad_diferente
        CHECK (modalidad_actual <> modalidad_propuesta),
    CONSTRAINT ck_cambio_modalidad_justificacion
        CHECK (trim(justificacion) <> ''),
    CONSTRAINT ck_cambio_modalidad_estado
        CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    CONSTRAINT ck_cambio_modalidad_resolucion
        CHECK (
            (estado = 'pendiente' AND resuelto_por_id IS NULL AND fecha_resolucion IS NULL)
            OR
            (estado IN ('aprobada', 'rechazada') AND resuelto_por_id IS NOT NULL AND fecha_resolucion IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cambio_modalidad_pendiente
    ON cpos.solicitudes_cambio_modalidad (proyecto_id)
    WHERE estado = 'pendiente';

ALTER TABLE cpos.aprobaciones
    DROP CONSTRAINT IF EXISTS ck_aprobaciones_tipo;

ALTER TABLE cpos.aprobaciones
    ADD CONSTRAINT ck_aprobaciones_tipo
    CHECK (tipo_aprobacion IN (
        'proyecto',
        'cambio_tema',
        'cambio_tutor',
        'reprogramacion',
        'cierre_proceso',
        'articulo',
        'archivo_proyecto',
        'cambio_modalidad'
    ));

ALTER TABLE cpos.evidencias
    DROP CONSTRAINT IF EXISTS ck_evidencias_tipo_avance;

ALTER TABLE cpos.evidencias
    ADD CONSTRAINT ck_evidencias_tipo_avance
    CHECK (tipo_avance IN (
        'busqueda_bibliografica',
        'titulo',
        'introduccion',
        'planteamiento_problema',
        'marco_teorico',
        'metodologia',
        'analisis',
        'resultados',
        'conclusiones',
        'referencias',
        'documento_final',
        'anexos',
        'plan_estudio',
        'banco_preguntas',
        'simulacion',
        'acta_resultado',
        'otro'
    ));

INSERT INTO cpos.permisos (
    codigo,
    nombre,
    modulo,
    descripcion,
    esta_activo,
    fecha_actualizacion
)
VALUES
    ('MODALIDAD_CONFIGURAR', 'Configurar modalidad por programa', 'titulacion', 'Configurar la opción Otra y sus requisitos por programa.', true, now()),
    ('CAMBIO_MODALIDAD_SOLICITAR', 'Solicitar cambio de modalidad', 'titulacion', 'Solicitar justificadamente un cambio después de aprobar el proyecto.', true, now()),
    ('CAMBIO_MODALIDAD_REVISAR', 'Revisar cambio de modalidad', 'titulacion', 'Aprobar o rechazar solicitudes dentro del programa coordinado.', true, now())
ON CONFLICT (codigo) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    modulo = EXCLUDED.modulo,
    descripcion = EXCLUDED.descripcion,
    esta_activo = true,
    fecha_actualizacion = now();

INSERT INTO cpos.rol_permiso (rol_id, permiso_id)
SELECT rol.id, permiso.id
FROM cpos.roles AS rol
JOIN cpos.permisos AS permiso ON (
    (permiso.codigo = 'MODALIDAD_CONFIGURAR' AND rol.nombre IN ('coordinador', 'administrador_desarrollador'))
    OR
    (permiso.codigo = 'CAMBIO_MODALIDAD_SOLICITAR' AND rol.nombre IN ('maestrante', 'tutor'))
    OR
    (permiso.codigo = 'CAMBIO_MODALIDAD_REVISAR' AND rol.nombre = 'coordinador')
)
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

COMMIT;

SELECT
    permiso.codigo,
    array_agg(rol.nombre ORDER BY rol.nombre) AS roles
FROM cpos.permisos AS permiso
LEFT JOIN cpos.rol_permiso AS rp ON rp.permiso_id = permiso.id
LEFT JOIN cpos.roles AS rol ON rol.id = rp.rol_id
WHERE permiso.codigo IN (
    'MODALIDAD_CONFIGURAR',
    'CAMBIO_MODALIDAD_SOLICITAR',
    'CAMBIO_MODALIDAD_REVISAR'
)
GROUP BY permiso.codigo
ORDER BY permiso.codigo;
