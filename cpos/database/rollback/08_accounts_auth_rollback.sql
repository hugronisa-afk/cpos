/*
===============================================================================
CPOS - ROLLBACK de la FASE 2 de autenticación
Archivo: database/rollback/08_accounts_auth_rollback.sql

ADVERTENCIA:
  - Elimina la columna nombre_usuario y, por tanto, los valores almacenados.
  - Restaura UNIQUE(cedula).
  - No puede ejecutarse si ya existen varias cuentas con la misma cédula.
  - No modifica correo ni contrasena_hash.

Debe revisarse y ejecutarse manualmente en Supabase únicamente si se decide
revertir por completo database/alter/08_accounts_auth.sql.
===============================================================================
*/

BEGIN;

-- 1. Comprobar que la tabla todavía exista.
DO $$
BEGIN
    IF to_regclass('cpos.usuarios') IS NULL THEN
        RAISE EXCEPTION
            'No existe la tabla cpos.usuarios. No es posible ejecutar el rollback.';
    END IF;
END
$$;

-- 2. Antes de restaurar UNIQUE(cedula), comprobar que ninguna cédula esté
-- repetida. Si existen cuentas de distintos roles para una misma persona, el
-- rollback se cancela sin realizar cambios.
DO $$
BEGIN
    IF EXISTS (
        SELECT cedula
        FROM cpos.usuarios
        GROUP BY cedula
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'No se puede restaurar UNIQUE(cedula): existen cédulas repetidas en cuentas de distintos roles.';
    END IF;
END
$$;

-- 3. Retirar las restricciones agregadas por el script de autenticación.
ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS uq_usuarios_nombre_usuario;

ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS ck_usuarios_nombre_usuario_formato;

ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS uq_usuarios_cedula_rol;

ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS ck_usuarios_cedula_formato;

-- 4. Restaurar la regla original de cédula única.
-- La restricción crea automáticamente su índice B-tree.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'cpos.usuarios'::regclass
          AND conname = 'uq_usuarios_cedula'
          AND contype = 'u'
    ) THEN
        EXECUTE $sql$
            ALTER TABLE cpos.usuarios
            ADD CONSTRAINT uq_usuarios_cedula
            UNIQUE (cedula)
        $sql$;
    END IF;
END
$$;

-- 5. Eliminar la columna agregada. Esta es la única operación del rollback
-- que descarta datos y por eso se realiza al final.
ALTER TABLE cpos.usuarios
    DROP COLUMN IF EXISTS nombre_usuario;

COMMIT;

/*
===============================================================================
COMPROBACIONES POSTERIORES AL ROLLBACK
===============================================================================
*/

-- Debe devolver cero filas: confirma que nombre_usuario ya no existe.
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'cpos'
  AND table_name = 'usuarios'
  AND column_name = 'nombre_usuario';

-- Confirmar que UNIQUE(cedula) volvió y UNIQUE(correo) permanece intacta.
SELECT
    c.conname AS restriccion,
    pg_get_constraintdef(c.oid) AS definicion
FROM pg_constraint AS c
WHERE c.conrelid = 'cpos.usuarios'::regclass
ORDER BY c.conname;
