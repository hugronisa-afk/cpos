/*
===============================================================================
CPOS - FASE 2: preparación de la tabla de usuarios para autenticación Django
Archivo: database/alter/08_accounts_auth.sql

Este script:
  1. Agrega cpos.usuarios.nombre_usuario.
  2. Genera el nombre como CEDULA-SIGLA_ROL para registros existentes.
  3. Conserva UNIQUE(correo), porque cada cuenta tendrá un correo diferente.
  4. Reemplaza UNIQUE(cedula) por UNIQUE(cedula, rol_id), permitiendo que una
     persona tenga cuentas de roles distintos, pero no dos del mismo rol.
  5. Agrega validaciones de formato y unicidad.

No modifica contrasena_hash y no ejecuta ninguna función de Supabase Auth.
Debe revisarse y ejecutarse manualmente en el editor SQL de Supabase.
===============================================================================
*/

BEGIN;

-- 1. Comprobar que la tabla objetivo exista en el esquema institucional.
DO $$
BEGIN
    IF to_regclass('cpos.usuarios') IS NULL THEN
        RAISE EXCEPTION
            'No existe la tabla cpos.usuarios. Verifique la base y el esquema antes de continuar.';
    END IF;
END
$$;

-- 2. Confirmar que la restricción de correo único que debe conservarse exista.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'cpos.usuarios'::regclass
          AND conname = 'uq_usuarios_correo'
          AND contype = 'u'
    ) THEN
        RAISE EXCEPTION
            'No se encontró uq_usuarios_correo. El script se detiene para no alterar una estructura inesperada.';
    END IF;
END
$$;

-- 3. Validar que todas las cédulas ya cumplan el formato institucional.
-- No se corrigen silenciosamente datos existentes.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM cpos.usuarios
        WHERE cedula IS NULL
           OR cedula = ''
           OR cedula !~ '^[0-9]+$'
    ) THEN
        RAISE EXCEPTION
            'Existen cédulas vacías o con caracteres no numéricos. Corríjalas antes de ejecutar este cambio.';
    END IF;
END
$$;

-- 4. Verificar que todos los usuarios tengan uno de los cuatro roles admitidos.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM cpos.usuarios AS u
        JOIN cpos.roles AS r ON r.id = u.rol_id
        WHERE lower(btrim(r.nombre)) NOT IN (
            'maestrante',
            'tutor',
            'coordinador',
            'supervisor'
        )
    ) THEN
        RAISE EXCEPTION
            'Existen usuarios con roles sin sigla configurada. Revise cpos.roles antes de continuar.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM cpos.usuarios AS u
        LEFT JOIN cpos.roles AS r ON r.id = u.rol_id
        WHERE r.id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Existen usuarios sin un rol válido. Corrija la relación antes de continuar.';
    END IF;
END
$$;

-- 5. Comprobar anticipadamente que los nombres generados no se repetirán.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM cpos.usuarios AS u
        JOIN cpos.roles AS r ON r.id = u.rol_id
        GROUP BY
            u.cedula,
            CASE lower(btrim(r.nombre))
                WHEN 'maestrante' THEN 'MST'
                WHEN 'tutor' THEN 'TTR'
                WHEN 'coordinador' THEN 'COR'
                WHEN 'supervisor' THEN 'SUP'
            END
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'La combinación cédula y rol contiene duplicados. No se puede generar un nombre de usuario único.';
    END IF;
END
$$;

-- 6. Agregar la columna. VARCHAR(30) cubre una cédula de hasta 20 caracteres,
-- el separador y la sigla de tres letras.
ALTER TABLE cpos.usuarios
    ADD COLUMN IF NOT EXISTS nombre_usuario varchar(30);

COMMENT ON COLUMN cpos.usuarios.nombre_usuario IS
    'Identificador de acceso generado como CEDULA-SIGLA_ROL. Se almacena en mayúsculas.';

-- 7. Completar únicamente registros sin nombre de usuario. Si el script se
-- vuelve a ejecutar, no sobrescribe valores que ya hayan sido establecidos.
UPDATE cpos.usuarios AS u
SET nombre_usuario = u.cedula || '-' ||
    CASE lower(btrim(r.nombre))
        WHEN 'maestrante' THEN 'MST'
        WHEN 'tutor' THEN 'TTR'
        WHEN 'coordinador' THEN 'COR'
        WHEN 'supervisor' THEN 'SUP'
    END
FROM cpos.roles AS r
WHERE r.id = u.rol_id
  AND (u.nombre_usuario IS NULL OR btrim(u.nombre_usuario) = '');

-- 8. Comprobar que cada valor coincida exactamente con la cédula y el rol.
-- Esto también detecta una ejecución parcial previa con datos inconsistentes.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM cpos.usuarios AS u
        JOIN cpos.roles AS r ON r.id = u.rol_id
        WHERE u.nombre_usuario IS DISTINCT FROM (
            u.cedula || '-' ||
            CASE lower(btrim(r.nombre))
                WHEN 'maestrante' THEN 'MST'
                WHEN 'tutor' THEN 'TTR'
                WHEN 'coordinador' THEN 'COR'
                WHEN 'supervisor' THEN 'SUP'
            END
        )
    ) THEN
        RAISE EXCEPTION
            'Uno o más nombres de usuario no coinciden con la regla CEDULA-SIGLA_ROL.';
    END IF;

    IF EXISTS (
        SELECT nombre_usuario
        FROM cpos.usuarios
        GROUP BY nombre_usuario
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Existen nombres de usuario duplicados. La transacción fue cancelada.';
    END IF;
END
$$;

-- 9. Después de completar y comprobar los datos, la columna pasa a obligatoria.
ALTER TABLE cpos.usuarios
    ALTER COLUMN nombre_usuario SET NOT NULL;

-- 10. Exigir cédula numérica, sin espacios ni guiones.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'cpos.usuarios'::regclass
          AND conname = 'ck_usuarios_cedula_formato'
    ) THEN
        EXECUTE $sql$
            ALTER TABLE cpos.usuarios
            ADD CONSTRAINT ck_usuarios_cedula_formato
            CHECK (cedula ~ '^[0-9]+$')
        $sql$;
    END IF;
END
$$;

-- 11. Exigir que el nombre esté en mayúsculas y use una sigla permitida.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'cpos.usuarios'::regclass
          AND conname = 'ck_usuarios_nombre_usuario_formato'
    ) THEN
        EXECUTE $sql$
            ALTER TABLE cpos.usuarios
            ADD CONSTRAINT ck_usuarios_nombre_usuario_formato
            CHECK (
                nombre_usuario = upper(nombre_usuario)
                AND nombre_usuario ~ '^[0-9]+-(MST|TTR|COR|SUP)$'
            )
        $sql$;
    END IF;
END
$$;

-- 12. La regla anterior UNIQUE(cedula) impide varias cuentas para una persona.
-- Se elimina únicamente esa restricción; no se elimina la columna ni sus datos.
ALTER TABLE cpos.usuarios
    DROP CONSTRAINT IF EXISTS uq_usuarios_cedula;

-- 13. Impedir que una misma cédula repita el mismo rol.
-- Esta restricción UNIQUE crea automáticamente su índice B-tree en PostgreSQL.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'cpos.usuarios'::regclass
          AND conname = 'uq_usuarios_cedula_rol'
          AND contype = 'u'
    ) THEN
        EXECUTE $sql$
            ALTER TABLE cpos.usuarios
            ADD CONSTRAINT uq_usuarios_cedula_rol
            UNIQUE (cedula, rol_id)
        $sql$;
    END IF;
END
$$;

-- 14. Garantizar que nombre_usuario sea único.
-- La restricción UNIQUE también crea el índice necesario para el login.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'cpos.usuarios'::regclass
          AND conname = 'uq_usuarios_nombre_usuario'
          AND contype = 'u'
    ) THEN
        EXECUTE $sql$
            ALTER TABLE cpos.usuarios
            ADD CONSTRAINT uq_usuarios_nombre_usuario
            UNIQUE (nombre_usuario)
        $sql$;
    END IF;
END
$$;

COMMENT ON CONSTRAINT uq_usuarios_cedula_rol ON cpos.usuarios IS
    'Evita repetir la misma combinación de cédula y rol.';

COMMENT ON CONSTRAINT uq_usuarios_nombre_usuario ON cpos.usuarios IS
    'Garantiza un nombre de inicio de sesión único.';

COMMIT;

/*
===============================================================================
CONSULTAS DE COMPROBACIÓN
Estas consultas son de solo lectura y pueden ejecutarse después del COMMIT.
No muestran contraseñas ni hashes.
===============================================================================
*/

-- Verificar los nombres generados sin consultar contrasena_hash.
SELECT
    u.id,
    u.cedula,
    r.nombre AS rol,
    u.nombre_usuario,
    u.correo,
    u.estado
FROM cpos.usuarios AS u
JOIN cpos.roles AS r ON r.id = u.rol_id
ORDER BY u.id;

-- La consulta debe devolver cero filas.
SELECT cedula, rol_id, count(*) AS cantidad
FROM cpos.usuarios
GROUP BY cedula, rol_id
HAVING count(*) > 1;

-- La consulta debe devolver cero filas.
SELECT nombre_usuario, count(*) AS cantidad
FROM cpos.usuarios
GROUP BY nombre_usuario
HAVING count(*) > 1;

-- Confirmar restricciones e índices creados.
SELECT
    c.conname AS restriccion,
    pg_get_constraintdef(c.oid) AS definicion
FROM pg_constraint AS c
WHERE c.conrelid = 'cpos.usuarios'::regclass
ORDER BY c.conname;

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'cpos'
  AND tablename = 'usuarios'
ORDER BY indexname;

-- Contar hashes reconocibles por Django sin revelar su contenido.
-- Los valores no compatibles deberán restablecerse desde la aplicación.
SELECT
    count(*) AS total_usuarios,
    count(*) FILTER (
        WHERE contrasena_hash ~
            '^(pbkdf2_sha256|pbkdf2_sha1|argon2|bcrypt_sha256|scrypt)\$'
    ) AS hashes_compatibles_django,
    count(*) FILTER (
        WHERE contrasena_hash !~
            '^(pbkdf2_sha256|pbkdf2_sha1|argon2|bcrypt_sha256|scrypt)\$'
    ) AS hashes_pendientes
FROM cpos.usuarios;
