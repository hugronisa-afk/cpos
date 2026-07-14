"""Servicios seguros y reutilizables para la aplicación ``accounts``."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import (
    Bitacora,
    EstadoUsuario,
    Permiso,
    Rol,
    UsuarioCPOS,
)


SIGLAS_ROL = {
    "maestrante": "MST",
    "tutor": "TTR",
    "coordinador": "COR",
    "supervisor": "SUP",
}

RUTAS_DASHBOARD_ROL = {
    "maestrante": "accounts:dashboard",
    "tutor": "accounts:dashboard",
    "coordinador": "accounts:dashboard",
    "supervisor": "accounts:dashboard",
}

BACKEND_USUARIO_CPOS = "apps.accounts.backends.UsuarioCPOSBackend"

_NO_PROPORCIONADO = object()
_PATRON_DATO_SENSIBLE = re.compile(
    r"(?i)\b(password|contrase(?:ña|na)|contrasena_hash|token|secret|secreto)"
    r"\b\s*[:=]\s*([^\s,;]+)"
)


def _texto_obligatorio(valor: Any, etiqueta: str, longitud_maxima: int) -> str:
    texto = str(valor or "").strip()
    if not texto:
        raise ValidationError({etiqueta: "Este campo es obligatorio."})
    if len(texto) > longitud_maxima:
        raise ValidationError(
            {etiqueta: f"No puede superar {longitud_maxima} caracteres."}
        )
    return texto


def _normalizar_cedula(cedula: Any) -> str:
    cedula_normalizada = re.sub(r"[\s-]+", "", str(cedula or ""))
    if not cedula_normalizada:
        raise ValidationError({"cedula": "La cédula es obligatoria."})
    if not cedula_normalizada.isdigit():
        raise ValidationError({"cedula": "La cédula debe contener solo números."})
    if len(cedula_normalizada) > 20:
        raise ValidationError({"cedula": "La cédula no puede superar 20 dígitos."})
    return cedula_normalizada


def _normalizar_correo(correo: Any) -> str:
    correo_normalizado = str(correo or "").strip().lower()
    if not correo_normalizado:
        raise ValidationError({"correo": "El correo es obligatorio."})
    if len(correo_normalizado) > 180:
        raise ValidationError({"correo": "El correo no puede superar 180 caracteres."})
    validate_email(correo_normalizado)
    return correo_normalizado


def _normalizar_telefono(telefono: Any) -> str | None:
    if telefono in (None, ""):
        return None
    telefono_normalizado = str(telefono).strip()
    if len(telefono_normalizado) > 30:
        raise ValidationError({"telefono": "El teléfono no puede superar 30 caracteres."})
    return telefono_normalizado or None


def _validar_password(password: Any, usuario: UsuarioCPOS) -> None:
    if not isinstance(password, str) or not password:
        raise ValidationError({"contrasena": "La contraseña es obligatoria."})
    password_validation.validate_password(password, user=usuario)


def _resolver_rol(rol: Rol | int | str) -> Rol:
    if isinstance(rol, Rol):
        rol_encontrado = rol
    elif isinstance(rol, int):
        rol_encontrado = Rol.objects.filter(pk=rol).first()
    else:
        rol_encontrado = Rol.objects.filter(nombre__iexact=str(rol).strip()).first()

    if rol_encontrado is None:
        raise ValidationError({"rol": "El rol indicado no existe."})
    return rol_encontrado


def _validar_rol_activo(rol: Rol) -> None:
    if not rol.esta_activo:
        raise ValidationError({"rol": "El rol indicado está inactivo."})


def _validar_estado_usuario(estado: str) -> str:
    estados_validos = {opcion for opcion, _ in EstadoUsuario.choices}
    if estado not in estados_validos:
        raise ValidationError({"estado": "El estado de usuario no es válido."})
    return estado


def _sanitizar_descripcion_bitacora(descripcion: Any) -> str | None:
    if descripcion in (None, ""):
        return None
    texto = str(descripcion).strip()
    return _PATRON_DATO_SENSIBLE.sub(r"\1=[PROTEGIDO]", texto)


def _usuario_actor(actor: Any = None, request: Any = None) -> UsuarioCPOS | None:
    if isinstance(actor, UsuarioCPOS):
        return actor
    usuario_request = getattr(request, "user", None)
    if isinstance(usuario_request, UsuarioCPOS):
        return usuario_request
    return None


def obtener_sigla_rol(rol: Rol | str) -> str:
    """Devuelve la sigla institucional correspondiente a un rol."""
    nombre_rol = rol.nombre if isinstance(rol, Rol) else str(rol)
    nombre_normalizado = nombre_rol.strip().lower()
    try:
        return SIGLAS_ROL[nombre_normalizado]
    except KeyError as exc:
        raise ValidationError({"rol": "El rol no tiene una sigla configurada."}) from exc


def generar_nombre_usuario(cedula: Any, rol: Rol | str) -> str:
    """Genera en backend un nombre ``CEDULA-SIGLA_ROL`` normalizado."""
    return f"{_normalizar_cedula(cedula)}-{obtener_sigla_rol(rol)}".upper()


def validar_nombre_usuario_disponible(
    nombre_usuario: str,
    excluir_usuario_id: int | None = None,
) -> bool:
    consulta = UsuarioCPOS.objects.filter(
        nombre_usuario__iexact=str(nombre_usuario).strip()
    )
    if excluir_usuario_id is not None:
        consulta = consulta.exclude(pk=excluir_usuario_id)
    return not consulta.exists()


def _validar_identificadores_disponibles(
    *,
    cedula: str,
    rol: Rol,
    correo: str,
    nombre_usuario: str,
    excluir_usuario_id: int | None = None,
) -> None:
    usuarios = UsuarioCPOS.objects.all()
    if excluir_usuario_id is not None:
        usuarios = usuarios.exclude(pk=excluir_usuario_id)

    errores = {}
    if usuarios.filter(cedula=cedula, rol=rol).exists():
        errores["cedula"] = "Ya existe una cuenta con esta cédula y este rol."
    if usuarios.filter(correo__iexact=correo).exists():
        errores["correo"] = "Ya existe una cuenta con este correo."
    if usuarios.filter(nombre_usuario__iexact=nombre_usuario).exists():
        errores["nombre_usuario"] = "El nombre de usuario ya está registrado."
    if errores:
        raise ValidationError(errores)


def crear_usuario_seguro(
    *,
    rol: Rol | int | str,
    nombres: str,
    apellidos: str,
    cedula: str,
    correo: str,
    contrasena: str,
    telefono: str | None = None,
    estado: str = EstadoUsuario.ACTIVO,
    actor: UsuarioCPOS | None = None,
    request: Any = None,
) -> UsuarioCPOS:
    """Crea una cuenta validada, con contraseña Django y auditoría atómica."""
    rol_objeto = _resolver_rol(rol)
    _validar_rol_activo(rol_objeto)
    cedula_normalizada = _normalizar_cedula(cedula)
    correo_normalizado = _normalizar_correo(correo)
    estado_validado = _validar_estado_usuario(estado)
    nombre_generado = generar_nombre_usuario(cedula_normalizada, rol_objeto)

    usuario = UsuarioCPOS(
        rol=rol_objeto,
        nombres=_texto_obligatorio(nombres, "nombres", 120),
        apellidos=_texto_obligatorio(apellidos, "apellidos", 120),
        cedula=cedula_normalizada,
        correo=correo_normalizado,
        telefono=_normalizar_telefono(telefono),
        estado=estado_validado,
        nombre_usuario=nombre_generado,
    )
    _validar_password(contrasena, usuario)
    usuario.set_password(contrasena)

    try:
        with transaction.atomic():
            _validar_identificadores_disponibles(
                cedula=cedula_normalizada,
                rol=rol_objeto,
                correo=correo_normalizado,
                nombre_usuario=nombre_generado,
            )
            usuario.save(force_insert=True)
            registrar_bitacora(
                usuario=_usuario_actor(actor, request),
                modulo="seguridad",
                accion="crear_usuario",
                tabla_afectada="usuarios",
                registro_id=usuario.pk,
                descripcion="Se creó una cuenta de usuario.",
                request=request,
            )
    except IntegrityError as exc:
        raise ValidationError(
            "No fue posible crear la cuenta porque uno de sus identificadores ya existe."
        ) from exc

    return usuario


def actualizar_usuario_seguro(
    usuario: UsuarioCPOS | int,
    *,
    rol: Rol | int | str | object = _NO_PROPORCIONADO,
    nombres: str | object = _NO_PROPORCIONADO,
    apellidos: str | object = _NO_PROPORCIONADO,
    cedula: str | object = _NO_PROPORCIONADO,
    correo: str | object = _NO_PROPORCIONADO,
    telefono: str | None | object = _NO_PROPORCIONADO,
    estado: str | object = _NO_PROPORCIONADO,
    actor: UsuarioCPOS | None = None,
    request: Any = None,
) -> UsuarioCPOS:
    """Actualiza campos permitidos y regenera el usuario si cambia rol/cédula."""
    usuario_id = usuario.pk if isinstance(usuario, UsuarioCPOS) else usuario
    campos_actualizados = []

    try:
        with transaction.atomic():
            usuario_actual = (
                UsuarioCPOS.objects.select_for_update()
                .select_related("rol")
                .get(pk=usuario_id)
            )

            rol_nuevo = (
                usuario_actual.rol if rol is _NO_PROPORCIONADO else _resolver_rol(rol)
            )
            _validar_rol_activo(rol_nuevo)
            cedula_nueva = (
                usuario_actual.cedula
                if cedula is _NO_PROPORCIONADO
                else _normalizar_cedula(cedula)
            )
            correo_nuevo = (
                usuario_actual.correo
                if correo is _NO_PROPORCIONADO
                else _normalizar_correo(correo)
            )
            nombre_generado = generar_nombre_usuario(cedula_nueva, rol_nuevo)

            _validar_identificadores_disponibles(
                cedula=cedula_nueva,
                rol=rol_nuevo,
                correo=correo_nuevo,
                nombre_usuario=nombre_generado,
                excluir_usuario_id=usuario_actual.pk,
            )

            valores = {
                "rol": rol_nuevo,
                "cedula": cedula_nueva,
                "correo": correo_nuevo,
                "nombre_usuario": nombre_generado,
            }
            if nombres is not _NO_PROPORCIONADO:
                valores["nombres"] = _texto_obligatorio(nombres, "nombres", 120)
            if apellidos is not _NO_PROPORCIONADO:
                valores["apellidos"] = _texto_obligatorio(apellidos, "apellidos", 120)
            if telefono is not _NO_PROPORCIONADO:
                valores["telefono"] = _normalizar_telefono(telefono)
            if estado is not _NO_PROPORCIONADO:
                valores["estado"] = _validar_estado_usuario(str(estado))

            for campo, valor in valores.items():
                if getattr(usuario_actual, campo) != valor:
                    setattr(usuario_actual, campo, valor)
                    campos_actualizados.append(campo)

            if campos_actualizados:
                usuario_actual.fecha_actualizacion = timezone.now()
                usuario_actual.save(
                    update_fields=campos_actualizados + ["fecha_actualizacion"]
                )
                registrar_bitacora(
                    usuario=_usuario_actor(actor, request),
                    modulo="seguridad",
                    accion="actualizar_usuario",
                    tabla_afectada="usuarios",
                    registro_id=usuario_actual.pk,
                    descripcion=(
                        "Se actualizaron campos de la cuenta: "
                        + ", ".join(sorted(campos_actualizados))
                        + "."
                    ),
                    request=request,
                )
    except UsuarioCPOS.DoesNotExist as exc:
        raise ValidationError({"usuario": "El usuario indicado no existe."}) from exc
    except IntegrityError as exc:
        raise ValidationError(
            "No fue posible actualizar la cuenta por una restricción de unicidad."
        ) from exc

    return usuario_actual


def cambiar_password_usuario(
    usuario: UsuarioCPOS | int,
    nueva_password: str,
    confirmacion_password: str,
    *,
    actor: UsuarioCPOS | None = None,
    request: Any = None,
    conservar_session_key: str | None = None,
) -> UsuarioCPOS:
    """Valida, cambia el hash y elimina las demás sesiones de la cuenta."""
    if nueva_password != confirmacion_password:
        raise ValidationError({"confirmacion_password": "Las contraseñas no coinciden."})

    usuario_id = usuario.pk if isinstance(usuario, UsuarioCPOS) else usuario
    try:
        with transaction.atomic():
            usuario_actual = UsuarioCPOS.objects.select_for_update().get(pk=usuario_id)
            _validar_password(nueva_password, usuario_actual)
            usuario_actual.set_password(nueva_password)
            usuario_actual.fecha_actualizacion = timezone.now()
            usuario_actual.save(
                update_fields=["contrasena_hash", "fecha_actualizacion"]
            )
            invalidar_sesiones_usuario(
                usuario_actual,
                excepto_session_key=conservar_session_key,
            )
            registrar_bitacora(
                usuario=_usuario_actor(actor, request),
                modulo="seguridad",
                accion="cambiar_password",
                tabla_afectada="usuarios",
                registro_id=usuario_actual.pk,
                descripcion="Se actualizó la contraseña de una cuenta.",
                request=request,
            )
    except UsuarioCPOS.DoesNotExist as exc:
        raise ValidationError({"usuario": "El usuario indicado no existe."}) from exc

    return usuario_actual


def verificar_password_usuario(usuario: UsuarioCPOS, password: str) -> bool:
    if not isinstance(usuario, UsuarioCPOS) or not password:
        return False
    return usuario.check_password(password)


def obtener_usuario_cpos(identificador: UsuarioCPOS | int | str) -> UsuarioCPOS | None:
    if isinstance(identificador, UsuarioCPOS):
        return identificador
    consulta = UsuarioCPOS.objects.select_related("rol")
    if isinstance(identificador, int):
        return consulta.filter(pk=identificador).first()
    return consulta.filter(
        nombre_usuario__iexact=str(identificador).strip()
    ).first()


def obtener_rol_usuario(usuario: UsuarioCPOS | int | str) -> Rol | None:
    usuario_cpos = obtener_usuario_cpos(usuario)
    return usuario_cpos.rol if usuario_cpos else None


def obtener_permisos_usuario(
    usuario: UsuarioCPOS | int | str,
) -> QuerySet[Permiso]:
    usuario_cpos = obtener_usuario_cpos(usuario)
    if not verificar_usuario_activo(usuario_cpos):
        return Permiso.objects.none()
    return (
        Permiso.objects.filter(
            esta_activo=True,
            asignaciones_roles__rol_id=usuario_cpos.rol_id,
            asignaciones_roles__rol__esta_activo=True,
        )
        .distinct()
        .order_by("modulo", "codigo")
    )


def usuario_tiene_rol(usuario: UsuarioCPOS | int | str, *roles: str) -> bool:
    usuario_cpos = obtener_usuario_cpos(usuario)
    if not verificar_usuario_activo(usuario_cpos) or not usuario_cpos.rol.esta_activo:
        return False
    roles_normalizados = {str(rol).strip().lower() for rol in roles}
    return usuario_cpos.rol.nombre.strip().lower() in roles_normalizados


def usuario_tiene_permiso(
    usuario: UsuarioCPOS | int | str,
    codigo_permiso: str,
) -> bool:
    codigo = str(codigo_permiso or "").strip().upper()
    if not codigo:
        return False
    return obtener_permisos_usuario(usuario).filter(codigo__iexact=codigo).exists()


def redireccion_por_rol(usuario: UsuarioCPOS | int | str) -> str:
    usuario_cpos = obtener_usuario_cpos(usuario)
    if not verificar_usuario_activo(usuario_cpos):
        return settings.LOGIN_URL
    rol = usuario_cpos.rol.nombre.strip().lower()
    return RUTAS_DASHBOARD_ROL.get(rol, settings.LOGIN_URL)


def registrar_bitacora(
    *,
    usuario: UsuarioCPOS | None,
    modulo: str,
    accion: str,
    tabla_afectada: str | None = None,
    registro_id: int | None = None,
    descripcion: str | None = None,
    request: Any = None,
) -> Bitacora:
    """Registra una acción sin aceptar volcados de formularios ni credenciales."""
    modulo_limpio = _texto_obligatorio(modulo, "modulo", 80)
    accion_limpia = _texto_obligatorio(accion, "accion", 120)
    tabla_limpia = str(tabla_afectada).strip()[:120] if tabla_afectada else None
    agente = None
    if request is not None:
        agente = str(request.META.get("HTTP_USER_AGENT", "")).strip() or None

    return Bitacora.objects.create(
        usuario=usuario if isinstance(usuario, UsuarioCPOS) else None,
        modulo=modulo_limpio,
        accion=accion_limpia,
        tabla_afectada=tabla_limpia,
        registro_id=registro_id,
        descripcion=_sanitizar_descripcion_bitacora(descripcion),
        direccion_ip=obtener_ip_cliente(request),
        agente_usuario=agente,
    )


def obtener_ip_cliente(request: Any) -> str | None:
    if request is None:
        return None

    ip_candidata = request.META.get("REMOTE_ADDR")
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        reenviadas = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if reenviadas:
            ip_candidata = reenviadas.split(",", 1)[0].strip()

    try:
        return str(ipaddress.ip_address(ip_candidata)) if ip_candidata else None
    except ValueError:
        return None


def invalidar_sesiones_usuario(
    usuario: UsuarioCPOS | int,
    *,
    excepto_session_key: str | None = None,
) -> int:
    """Elimina únicamente sesiones creadas por el futuro backend CPOS."""
    usuario_id = usuario.pk if isinstance(usuario, UsuarioCPOS) else usuario
    sesiones_a_eliminar = []

    for sesion in Session.objects.filter(expire_date__gte=timezone.now()).iterator():
        datos = sesion.get_decoded()
        if (
            datos.get("_auth_user_backend") == BACKEND_USUARIO_CPOS
            and str(datos.get("_auth_user_id")) == str(usuario_id)
            and sesion.session_key != excepto_session_key
        ):
            sesiones_a_eliminar.append(sesion.session_key)

    if not sesiones_a_eliminar:
        return 0
    eliminadas, _ = Session.objects.filter(
        session_key__in=sesiones_a_eliminar
    ).delete()
    return eliminadas


def verificar_usuario_activo(usuario: Any) -> bool:
    return bool(
        isinstance(usuario, UsuarioCPOS)
        and usuario.is_active
        and not usuario.esta_bloqueado
        and usuario.rol.esta_activo
    )
