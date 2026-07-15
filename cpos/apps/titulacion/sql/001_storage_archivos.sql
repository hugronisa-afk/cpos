BEGIN;

ALTER TABLE cpos.aprobaciones
    DROP CONSTRAINT IF EXISTS ck_aprobaciones_tipo;

ALTER TABLE cpos.aprobaciones
    ADD CONSTRAINT ck_aprobaciones_tipo
    CHECK (
        tipo_aprobacion::text = ANY (
            ARRAY[
                'proyecto',
                'cambio_tema',
                'cambio_tutor',
                'reprogramacion',
                'cierre_proceso',
                'articulo',
                'archivo_proyecto'
            ]::text[]
        )
    );

ALTER TABLE cpos.grabaciones
    ADD COLUMN IF NOT EXISTS nombre_original varchar(255),
    ADD COLUMN IF NOT EXISTS extension varchar(10),
    ADD COLUMN IF NOT EXISTS tamano_bytes bigint;

ALTER TABLE cpos.grabaciones
    DROP CONSTRAINT IF EXISTS ck_grabaciones_metadata_archivo;

ALTER TABLE cpos.grabaciones
    ADD CONSTRAINT ck_grabaciones_metadata_archivo
    CHECK (
        tipo_grabacion <> 'archivo'
        OR (
            nombre_original IS NOT NULL
            AND btrim(nombre_original) <> ''
            AND extension IS NOT NULL
            AND btrim(extension) <> ''
            AND tamano_bytes > 0
        )
    );

INSERT INTO storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
VALUES (
    'titulacion-privado',
    'titulacion-privado',
    false,
    524288000,
    ARRAY[
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'video/mp4',
        'video/webm',
        'audio/mpeg',
        'audio/mp4',
        'audio/webm'
    ]
)
ON CONFLICT (id) DO UPDATE
SET
    public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

COMMIT;
