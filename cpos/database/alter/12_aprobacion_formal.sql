/*
CPOS - FASE 4
Revisión formal versionada, documentos obligatorios y aprobación por etapas.
*/

BEGIN;

CREATE TABLE IF NOT EXISTS cpos.procesos_aprobacion (
    id bigserial PRIMARY KEY,
    proyecto_id bigint NOT NULL,
    tipo varchar(40) NOT NULL,
    referencia_tabla varchar(100) NOT NULL,
    referencia_id bigint NOT NULL,
    numero_version smallint NOT NULL DEFAULT 1,
    estado varchar(30) NOT NULL DEFAULT 'en_curso',
    paso_actual smallint NOT NULL DEFAULT 1,
    creado_por_id bigint NULL,
    fecha_finalizacion timestamptz NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_proceso_aprobacion_proyecto
        FOREIGN KEY (proyecto_id) REFERENCES cpos.proyectos_titulacion(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_proceso_aprobacion_creado_por
        FOREIGN KEY (creado_por_id) REFERENCES cpos.usuarios(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_proceso_aprobacion_version
        UNIQUE (tipo, referencia_tabla, referencia_id, numero_version),
    CONSTRAINT ck_proceso_aprobacion_tipo
        CHECK (tipo IN ('proyecto', 'cambio_tema', 'cambio_modalidad')),
    CONSTRAINT ck_proceso_aprobacion_version
        CHECK (numero_version >= 1),
    CONSTRAINT ck_proceso_aprobacion_estado
        CHECK (estado IN ('en_curso', 'observado', 'aprobado', 'rechazado', 'cancelado')),
    CONSTRAINT ck_proceso_aprobacion_paso
        CHECK (paso_actual >= 1),
    CONSTRAINT ck_proceso_aprobacion_finalizacion
        CHECK (
            (estado = 'en_curso' AND fecha_finalizacion IS NULL)
            OR
            (estado <> 'en_curso' AND fecha_finalizacion IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_proceso_aprobacion_activo_proyecto
    ON cpos.procesos_aprobacion (proyecto_id)
    WHERE estado = 'en_curso';

CREATE TABLE IF NOT EXISTS cpos.pasos_aprobacion (
    id bigserial PRIMARY KEY,
    proceso_id bigint NOT NULL,
    orden smallint NOT NULL,
    codigo varchar(60) NOT NULL,
    nombre varchar(150) NOT NULL,
    instancia varchar(150) NOT NULL,
    rol_responsable varchar(50) NOT NULL,
    estado varchar(30) NOT NULL DEFAULT 'pendiente',
    resuelto_por_id bigint NULL,
    observaciones text NULL,
    fecha_resolucion timestamptz NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_paso_aprobacion_proceso
        FOREIGN KEY (proceso_id) REFERENCES cpos.procesos_aprobacion(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_paso_aprobacion_resuelto_por
        FOREIGN KEY (resuelto_por_id) REFERENCES cpos.usuarios(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT uq_paso_aprobacion_orden UNIQUE (proceso_id, orden),
    CONSTRAINT uq_paso_aprobacion_codigo UNIQUE (proceso_id, codigo),
    CONSTRAINT ck_paso_aprobacion_orden CHECK (orden >= 1),
    CONSTRAINT ck_paso_aprobacion_codigo CHECK (trim(codigo) <> ''),
    CONSTRAINT ck_paso_aprobacion_nombre CHECK (trim(nombre) <> ''),
    CONSTRAINT ck_paso_aprobacion_instancia CHECK (trim(instancia) <> ''),
    CONSTRAINT ck_paso_aprobacion_rol
        CHECK (rol_responsable IN ('coordinador', 'supervisor')),
    CONSTRAINT ck_paso_aprobacion_estado
        CHECK (estado IN ('pendiente', 'activo', 'aprobado', 'observado', 'rechazado')),
    CONSTRAINT ck_paso_aprobacion_resolucion
        CHECK (
            (estado IN ('pendiente', 'activo') AND resuelto_por_id IS NULL AND fecha_resolucion IS NULL)
            OR
            (estado IN ('aprobado', 'observado', 'rechazado') AND resuelto_por_id IS NOT NULL AND fecha_resolucion IS NOT NULL)
        )
);

CREATE TABLE IF NOT EXISTS cpos.documentos_proceso_aprobacion (
    id bigserial PRIMARY KEY,
    proceso_id bigint NOT NULL,
    archivo_id bigint NOT NULL,
    tipo_documento varchar(30) NOT NULL,
    fecha_creacion timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_documento_proceso_aprobacion_proceso
        FOREIGN KEY (proceso_id) REFERENCES cpos.procesos_aprobacion(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_documento_proceso_aprobacion_archivo
        FOREIGN KEY (archivo_id) REFERENCES cpos.archivos_proyecto(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_documento_proceso_tipo UNIQUE (proceso_id, tipo_documento),
    CONSTRAINT ck_documento_proceso_tipo
        CHECK (tipo_documento IN ('word', 'pdf', 'respaldo', 'resolucion'))
);

INSERT INTO cpos.permisos (
    codigo,
    nombre,
    modulo,
    descripcion,
    esta_activo,
    fecha_actualizacion
)
VALUES
    ('APROBACION_FORMAL_VER', 'Ver aprobación formal', 'titulacion', 'Consultar procesos, documentos y decisiones por etapa.', true, now()),
    ('APROBACION_COORDINACION', 'Resolver etapas de coordinación', 'titulacion', 'Resolver visto bueno, comisión y unidad de titulación dentro del programa.', true, now()),
    ('APROBACION_SUPERVISION', 'Resolver aprobación institucional', 'titulacion', 'Resolver consejo de posgrado y aprobación institucional final.', true, now()),
    ('PROYECTO_RESOLUCION_REGISTRAR', 'Registrar resolución oficial', 'titulacion', 'Registrar número, fecha y PDF de la resolución de un proyecto aprobado.', true, now())
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
    (permiso.codigo = 'APROBACION_FORMAL_VER' AND rol.nombre IN ('maestrante', 'tutor', 'coordinador', 'supervisor'))
    OR (permiso.codigo = 'APROBACION_COORDINACION' AND rol.nombre = 'coordinador')
    OR (permiso.codigo = 'APROBACION_SUPERVISION' AND rol.nombre = 'supervisor')
    OR (permiso.codigo = 'PROYECTO_RESOLUCION_REGISTRAR' AND rol.nombre = 'coordinador')
)
ON CONFLICT (rol_id, permiso_id) DO NOTHING;

/* Coordinación revisa, pero ya no emite la aprobación institucional final. */
DELETE FROM cpos.rol_permiso rp
USING cpos.roles rol, cpos.permisos permiso
WHERE rp.rol_id = rol.id
  AND rp.permiso_id = permiso.id
  AND rol.nombre = 'coordinador'
  AND permiso.codigo = 'PROYECTO_APROBAR';

/* Supervisión conserva lectura y decisiones finales, no operaciones académicas. */
DELETE FROM cpos.rol_permiso rp
USING cpos.roles rol, cpos.permisos permiso
WHERE rp.rol_id = rol.id
  AND rp.permiso_id = permiso.id
  AND rol.nombre = 'supervisor'
  AND permiso.codigo IN (
      'ARCHIVO_SUBIR', 'ARTICULO_EDITAR', 'ASIGNACION_TUTOR_CAMBIAR',
      'ASIGNACION_TUTOR_CREAR', 'ASISTENCIA_REGISTRAR', 'CAMBIO_TEMA_SOLICITAR',
      'EVIDENCIA_EDITAR', 'EVIDENCIA_OBSERVAR', 'EVIDENCIA_SUBIR',
      'EVIDENCIA_VALIDAR', 'GRABACION_REGISTRAR', 'PROYECTO_CREAR',
      'PROYECTO_EDITAR', 'REPROGRAMACION_GESTIONAR', 'REPROGRAMACION_SOLICITAR',
      'TUTOR_CREAR', 'TUTOR_EDITAR', 'TUTORIA_EDITAR', 'TUTORIA_PROGRAMAR',
      'USUARIO_CREAR', 'USUARIO_DESACTIVAR', 'USUARIO_EDITAR'
  );

/* Adopta revisiones existentes que ya tienen Word y PDF. */
INSERT INTO cpos.procesos_aprobacion (
    proyecto_id,
    tipo,
    referencia_tabla,
    referencia_id,
    numero_version,
    estado,
    paso_actual,
    creado_por_id
)
SELECT
    proyecto.id,
    'proyecto',
    'proyectos_titulacion',
    proyecto.id,
    1,
    'en_curso',
    1,
    proyecto.creado_por_id
FROM cpos.proyectos_titulacion proyecto
WHERE proyecto.estado = 'en_revision'
  AND EXISTS (
      SELECT 1 FROM cpos.archivos_proyecto archivo
      WHERE archivo.proyecto_id = proyecto.id AND archivo.tipo_archivo = 'word'
  )
  AND EXISTS (
      SELECT 1 FROM cpos.archivos_proyecto archivo
      WHERE archivo.proyecto_id = proyecto.id AND archivo.tipo_archivo = 'pdf'
  )
  AND NOT EXISTS (
      SELECT 1 FROM cpos.procesos_aprobacion proceso
      WHERE proceso.tipo = 'proyecto'
        AND proceso.referencia_tabla = 'proyectos_titulacion'
        AND proceso.referencia_id = proyecto.id
  );

INSERT INTO cpos.pasos_aprobacion (
    proceso_id, orden, codigo, nombre, instancia, rol_responsable, estado
)
SELECT
    proceso.id,
    paso.orden,
    paso.codigo,
    paso.nombre,
    paso.instancia,
    paso.rol_responsable,
    CASE WHEN paso.orden = 1 THEN 'activo' ELSE 'pendiente' END
FROM cpos.procesos_aprobacion proceso
CROSS JOIN (VALUES
    (1, 'visto_bueno_inicial', 'Visto bueno inicial', 'Coordinación del programa', 'coordinador'),
    (2, 'revision_comision', 'Revisión de comisión', 'Comisión académica de titulación', 'coordinador'),
    (3, 'aprobacion_supervisor', 'Aprobación institucional final', 'Supervisión general', 'supervisor')
) AS paso(orden, codigo, nombre, instancia, rol_responsable)
WHERE proceso.tipo = 'proyecto'
  AND NOT EXISTS (
      SELECT 1 FROM cpos.pasos_aprobacion existente
      WHERE existente.proceso_id = proceso.id
  );

INSERT INTO cpos.documentos_proceso_aprobacion (
    proceso_id, archivo_id, tipo_documento
)
SELECT proceso.id, archivo.id, tipo.tipo_documento
FROM cpos.procesos_aprobacion proceso
CROSS JOIN (VALUES ('word'), ('pdf')) AS tipo(tipo_documento)
JOIN LATERAL (
    SELECT candidato.id
    FROM cpos.archivos_proyecto candidato
    WHERE candidato.proyecto_id = proceso.proyecto_id
      AND candidato.tipo_archivo = tipo.tipo_documento
    ORDER BY candidato.fecha_creacion DESC, candidato.id DESC
    LIMIT 1
) archivo ON true
WHERE proceso.tipo = 'proyecto'
ON CONFLICT (proceso_id, tipo_documento) DO NOTHING;

/* La aprobación pendiente anterior pasa a representar el primer paso formal. */
UPDATE cpos.aprobaciones aprobacion
SET referencia_tabla = 'pasos_aprobacion',
    referencia_id = paso.id
FROM cpos.procesos_aprobacion proceso
JOIN cpos.pasos_aprobacion paso
  ON paso.proceso_id = proceso.id AND paso.orden = 1
WHERE aprobacion.proyecto_id = proceso.proyecto_id
  AND aprobacion.tipo_aprobacion = 'proyecto'
  AND aprobacion.estado = 'pendiente'
  AND aprobacion.referencia_tabla = 'proyectos_titulacion'
  AND aprobacion.referencia_id = proceso.proyecto_id;

INSERT INTO cpos.aprobaciones (
    proyecto_id, tipo_aprobacion, referencia_tabla, referencia_id, estado
)
SELECT proceso.proyecto_id, proceso.tipo, 'pasos_aprobacion', paso.id, 'pendiente'
FROM cpos.procesos_aprobacion proceso
JOIN cpos.pasos_aprobacion paso
  ON paso.proceso_id = proceso.id AND paso.estado = 'activo'
WHERE NOT EXISTS (
    SELECT 1 FROM cpos.aprobaciones aprobacion
    WHERE aprobacion.referencia_tabla = 'pasos_aprobacion'
      AND aprobacion.referencia_id = paso.id
      AND aprobacion.estado = 'pendiente'
);

/* Ninguna revisión antigua queda bloqueada si le falta un documento obligatorio. */
WITH sin_documentos AS (
    SELECT proyecto.id
    FROM cpos.proyectos_titulacion proyecto
    WHERE proyecto.estado = 'en_revision'
      AND NOT EXISTS (
          SELECT 1 FROM cpos.procesos_aprobacion proceso
          WHERE proceso.proyecto_id = proyecto.id AND proceso.estado = 'en_curso'
      )
)
UPDATE cpos.proyectos_titulacion proyecto
SET estado = 'observado',
    observaciones = 'Debe cargar las versiones Word y PDF antes de reenviar a revisión.',
    fecha_actualizacion = now()
FROM sin_documentos
WHERE proyecto.id = sin_documentos.id;

UPDATE cpos.aprobaciones aprobacion
SET estado = 'observado',
    observaciones = 'Revisión migrada: faltan Word y PDF obligatorios.'
FROM cpos.proyectos_titulacion proyecto
WHERE aprobacion.proyecto_id = proyecto.id
  AND aprobacion.tipo_aprobacion = 'proyecto'
  AND aprobacion.estado = 'pendiente'
  AND proyecto.estado = 'observado';

COMMIT;

SELECT
    proceso.id,
    proceso.proyecto_id,
    proceso.tipo,
    proceso.numero_version,
    proceso.estado,
    count(DISTINCT paso.id) AS pasos,
    count(DISTINCT documento.id) AS documentos
FROM cpos.procesos_aprobacion proceso
LEFT JOIN cpos.pasos_aprobacion paso ON paso.proceso_id = proceso.id
LEFT JOIN cpos.documentos_proceso_aprobacion documento
    ON documento.proceso_id = proceso.id
GROUP BY proceso.id
ORDER BY proceso.id;
