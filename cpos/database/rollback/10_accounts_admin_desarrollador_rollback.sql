/* Reversión segura de la fase 2. Se detiene si existen cuentas técnicas. */

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM cpos.usuarios AS usuario
        JOIN cpos.roles AS rol ON rol.id = usuario.rol_id
        WHERE rol.nombre = 'administrador_desarrollador'
    ) THEN
        RAISE EXCEPTION
            'Existen cuentas administrador/desarrollador. Reasígnelas antes de revertir.';
    END IF;
END
$$;

DELETE FROM cpos.rol_permiso
WHERE rol_id = (
    SELECT id FROM cpos.roles WHERE nombre = 'administrador_desarrollador'
);

DELETE FROM cpos.roles
WHERE nombre = 'administrador_desarrollador';

DELETE FROM cpos.permisos
WHERE codigo IN (
    'IMPORTACION_USUARIOS',
    'MANTENIMIENTO_VER',
    'MANTENIMIENTO_EJECUTAR'
)
AND NOT EXISTS (
    SELECT 1
    FROM cpos.rol_permiso
    WHERE permiso_id = cpos.permisos.id
);

ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS ck_usuarios_nombre_usuario_formato;

ALTER TABLE cpos.usuarios
    ADD CONSTRAINT ck_usuarios_nombre_usuario_formato
    CHECK (
        nombre_usuario = upper(nombre_usuario)
        AND nombre_usuario ~ '^[0-9]+-(MST|TTR|COR|SUP)$'
    );

COMMIT;
