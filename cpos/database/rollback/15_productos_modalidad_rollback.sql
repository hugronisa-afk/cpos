/*
Reversión segura de la Fase 7: onboarding, modalidades configuradas,
etapas/entregas de producto, novena tutoría excepcional, examen complexivo
y escalas de calificación. No toca datos de fases anteriores (1-6).
*/

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM cpos.entregas_etapa WHERE estado = 'aprobada') THEN
        RAISE EXCEPTION
            'Existen entregas de etapa aprobadas. Expórtelas antes de revertir.';
    END IF;
    IF EXISTS (SELECT 1 FROM cpos.examenes_complexivos WHERE resultado <> 'pendiente') THEN
        RAISE EXCEPTION
            'Existen exámenes complexivos con resultado registrado. No se pueden descartar.';
    END IF;
    IF EXISTS (SELECT 1 FROM cpos.onboarding_maestrantes WHERE estado = 'completado') THEN
        RAISE EXCEPTION
            'Existen onboardings completados. No se pueden descartar sin exportar.';
    END IF;
END $$;

-- Triggers y funciones
DROP TRIGGER IF EXISTS trg_fase7_entrega_aprobada ON cpos.entregas_etapa;
DROP TRIGGER IF EXISTS trg_fase7_orden_etapas ON cpos.entregas_etapa;
DROP TRIGGER IF EXISTS trg_fase7_novena_tutoria ON cpos.tutorias;
DROP FUNCTION IF EXISTS cpos.fase7_proteger_entrega_aprobada();
DROP FUNCTION IF EXISTS cpos.fase7_validar_orden_etapas();
DROP FUNCTION IF EXISTS cpos.fase7_validar_novena_tutoria();

-- Restaura el CHECK original de Fase 6 (1-8) antes de soltar la columna
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cpos.tutorias'::regclass
          AND conname = 'ck_tutorias_numero_nueve'
    ) THEN
        ALTER TABLE cpos.tutorias DROP CONSTRAINT ck_tutorias_numero_nueve;
    END IF;
    IF EXISTS (SELECT 1 FROM cpos.tutorias WHERE numero_tutoria = 9) THEN
        RAISE EXCEPTION
            'Existen tutorías con numero_tutoria = 9. No se puede restaurar el límite de 8 sin resolverlas.';
    END IF;
    ALTER TABLE cpos.tutorias
        ADD CONSTRAINT ck_tutorias_numero_ocho
        CHECK (numero_tutoria BETWEEN 1 AND 8);
END $$;

ALTER TABLE cpos.tutorias DROP COLUMN IF EXISTS es_excepcional;

-- Tablas (orden inverso de dependencias)
DROP TABLE IF EXISTS cpos.autorizaciones_novena_tutoria;
DROP TABLE IF EXISTS cpos.examenes_complexivos;
DROP TABLE IF EXISTS cpos.escalas_calificacion;
DROP TABLE IF EXISTS cpos.entregas_etapa;
DROP TABLE IF EXISTS cpos.etapas_producto;
DROP TABLE IF EXISTS cpos.modalidades_configuradas;
DROP TABLE IF EXISTS cpos.onboarding_maestrantes;

ALTER TABLE cpos.maestrantes DROP COLUMN IF EXISTS modulo_actual;

-- Permisos nuevos de Fase 7 (conserva MODALIDAD_CONFIGURAR, ya existía en Fase 3)
DELETE FROM cpos.rol_permiso
WHERE permiso_id IN (
    SELECT id FROM cpos.permisos WHERE codigo IN (
        'ONBOARDING_GESTIONAR',
        'ONBOARDING_CONSULTAR',
        'MODALIDAD_ETAPAS_CONFIGURAR',
        'MODALIDAD_ETAPAS_CONSULTAR',
        'ENTREGA_ETAPA_SUBIR',
        'ENTREGA_ETAPA_EVALUAR',
        'ENTREGA_ETAPA_CONSULTAR',
        'TUTOR_ASIGNAR',
        'NOVENA_TUTORIA_AUTORIZAR',
        'EXAMEN_COMPLEXIVO_GESTIONAR',
        'EXAMEN_COMPLEXIVO_CONSULTAR',
        'ESCALA_CALIFICACION_CONFIGURAR'
    )
);

-- Retira la extensión de MODALIDAD_CONFIGURAR al rol supervisor (deja intacto
-- el permiso para coordinador/administrador_desarrollador, que es de Fase 3).
DELETE FROM cpos.rol_permiso
WHERE permiso_id IN (SELECT id FROM cpos.permisos WHERE codigo = 'MODALIDAD_CONFIGURAR')
  AND rol_id IN (SELECT id FROM cpos.roles WHERE nombre = 'supervisor');

DELETE FROM cpos.permisos WHERE codigo IN (
    'ONBOARDING_GESTIONAR',
    'ONBOARDING_CONSULTAR',
    'MODALIDAD_ETAPAS_CONFIGURAR',
    'MODALIDAD_ETAPAS_CONSULTAR',
    'ENTREGA_ETAPA_SUBIR',
    'ENTREGA_ETAPA_EVALUAR',
    'ENTREGA_ETAPA_CONSULTAR',
    'TUTOR_ASIGNAR',
    'NOVENA_TUTORIA_AUTORIZAR',
    'EXAMEN_COMPLEXIVO_GESTIONAR',
    'EXAMEN_COMPLEXIVO_CONSULTAR',
    'ESCALA_CALIFICACION_CONFIGURAR'
);

COMMIT;
