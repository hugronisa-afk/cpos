/* Reversión de la fase 3. Elimina configuración e historial de modalidad. */

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM cpos.evidencias
        WHERE tipo_avance NOT IN (
            'busqueda_bibliografica', 'titulo', 'introduccion', 'metodologia',
            'resultados', 'conclusiones', 'referencias', 'otro'
        )
    ) THEN
        RAISE EXCEPTION
            'Existen evidencias con categorías de la fase 3. Reclasifíquelas antes de revertir.';
    END IF;
END
$$;

DELETE FROM cpos.aprobaciones
WHERE tipo_aprobacion = 'cambio_modalidad';

DROP TABLE IF EXISTS cpos.solicitudes_cambio_modalidad;
DROP TABLE IF EXISTS cpos.configuraciones_modalidad_programa;

ALTER TABLE cpos.aprobaciones
    DROP CONSTRAINT IF EXISTS ck_aprobaciones_tipo;

ALTER TABLE cpos.aprobaciones
    ADD CONSTRAINT ck_aprobaciones_tipo
    CHECK (tipo_aprobacion IN (
        'proyecto', 'cambio_tema', 'cambio_tutor', 'reprogramacion',
        'cierre_proceso', 'articulo', 'archivo_proyecto'
    ));

ALTER TABLE cpos.evidencias
    DROP CONSTRAINT IF EXISTS ck_evidencias_tipo_avance;

ALTER TABLE cpos.evidencias
    ADD CONSTRAINT ck_evidencias_tipo_avance
    CHECK (tipo_avance IN (
        'busqueda_bibliografica', 'titulo', 'introduccion', 'metodologia',
        'resultados', 'conclusiones', 'referencias', 'otro'
    ));

DELETE FROM cpos.rol_permiso
WHERE permiso_id IN (
    SELECT id
    FROM cpos.permisos
    WHERE codigo IN (
        'MODALIDAD_CONFIGURAR',
        'CAMBIO_MODALIDAD_SOLICITAR',
        'CAMBIO_MODALIDAD_REVISAR'
    )
);

DELETE FROM cpos.permisos
WHERE codigo IN (
    'MODALIDAD_CONFIGURAR',
    'CAMBIO_MODALIDAD_SOLICITAR',
    'CAMBIO_MODALIDAD_REVISAR'
);

COMMIT;
