"""Decoradores y mixins de autorización para las vistas de CPOS."""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.contrib.messages.api import MessageFailure
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.shortcuts import resolve_url

from .models import UsuarioCPOS
from .services import (
    usuario_tiene_permiso,
    usuario_tiene_rol,
    verificar_usuario_activo,
)


MENSAJE_SESION_REQUERIDA = "Debe iniciar sesión para acceder a esta página."
MENSAJE_CUENTA_NO_DISPONIBLE = (
    "Su cuenta no está disponible. Comuníquese con el administrador del sistema."
)
MENSAJE_ACCESO_DENEGADO = "No tiene autorización para realizar esta acción."


def _agregar_mensaje_error(request, mensaje):
    try:
        messages.error(request, mensaje)
    except MessageFailure:
        # Las vistas reales usan MessageMiddleware. Esta protección permite que
        # el decorador siga siendo seguro en pruebas unitarias aisladas.
        return None
    return True


def _respuesta_login(request, login_url=None):
    return redirect_to_login(
        request.get_full_path(),
        resolve_url(login_url or settings.LOGIN_URL),
    )


def _obtener_usuario_activo(request, login_url=None):
    usuario = getattr(request, "user", None)
    if not getattr(usuario, "is_authenticated", False):
        _agregar_mensaje_error(request, MENSAJE_SESION_REQUERIDA)
        return None, _respuesta_login(request, login_url)

    if not isinstance(usuario, UsuarioCPOS) or not verificar_usuario_activo(usuario):
        if hasattr(request, "session"):
            logout(request)
        _agregar_mensaje_error(request, MENSAJE_CUENTA_NO_DISPONIBLE)
        return None, _respuesta_login(request, login_url)

    return usuario, None


def usuario_activo_required(view_func=None, *, login_url=None):
    """Exige una sesión institucional perteneciente a una cuenta activa."""

    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            _, respuesta = _obtener_usuario_activo(request, login_url)
            if respuesta is not None:
                return respuesta
            return func(request, *args, **kwargs)

        return wrapped

    if view_func is None:
        return decorator
    return decorator(view_func)


def rol_required(*roles, login_url=None):
    """Exige al menos uno de los roles indicados, además de una cuenta activa."""
    roles_normalizados = tuple(
        str(rol).strip().lower() for rol in roles if str(rol).strip()
    )
    if not roles_normalizados:
        raise ValueError("rol_required necesita al menos un rol.")

    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            usuario, respuesta = _obtener_usuario_activo(request, login_url)
            if respuesta is not None:
                return respuesta
            if not usuario_tiene_rol(usuario, *roles_normalizados):
                raise PermissionDenied(MENSAJE_ACCESO_DENEGADO)
            return func(request, *args, **kwargs)

        return wrapped

    return decorator


def permiso_required(codigo_permiso, *, login_url=None):
    """Exige un permiso efectivo y activo asignado al rol del usuario."""
    codigo = str(codigo_permiso or "").strip().upper()
    if not codigo:
        raise ValueError("permiso_required necesita un código de permiso.")

    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            usuario, respuesta = _obtener_usuario_activo(request, login_url)
            if respuesta is not None:
                return respuesta
            if not usuario_tiene_permiso(usuario, codigo):
                raise PermissionDenied(MENSAJE_ACCESO_DENEGADO)
            return func(request, *args, **kwargs)

        return wrapped

    return decorator


class UsuarioActivoRequiredMixin:
    """Versión reutilizable de ``usuario_activo_required`` para CBV."""

    login_url = None

    def dispatch(self, request, *args, **kwargs):
        usuario, respuesta = _obtener_usuario_activo(request, self.login_url)
        if respuesta is not None:
            return respuesta
        self.usuario_cpos = usuario
        return super().dispatch(request, *args, **kwargs)


class RolRequiredMixin:
    """Protección por rol para vistas basadas en clases."""

    roles_permitidos = ()
    login_url = None

    def get_roles_permitidos(self):
        roles = tuple(
            str(rol).strip().lower()
            for rol in self.roles_permitidos
            if str(rol).strip()
        )
        if not roles:
            raise ImproperlyConfigured(
                "RolRequiredMixin necesita definir roles_permitidos."
            )
        return roles

    def dispatch(self, request, *args, **kwargs):
        usuario, respuesta = _obtener_usuario_activo(request, self.login_url)
        if respuesta is not None:
            return respuesta
        if not usuario_tiene_rol(usuario, *self.get_roles_permitidos()):
            raise PermissionDenied(MENSAJE_ACCESO_DENEGADO)
        self.usuario_cpos = usuario
        return super().dispatch(request, *args, **kwargs)


class PermisoRequiredMixin:
    """Protección por permiso efectivo para vistas basadas en clases."""

    permiso_requerido = None
    login_url = None

    def get_permiso_requerido(self):
        codigo = str(self.permiso_requerido or "").strip().upper()
        if not codigo:
            raise ImproperlyConfigured(
                "PermisoRequiredMixin necesita definir permiso_requerido."
            )
        return codigo

    def dispatch(self, request, *args, **kwargs):
        usuario, respuesta = _obtener_usuario_activo(request, self.login_url)
        if respuesta is not None:
            return respuesta
        if not usuario_tiene_permiso(usuario, self.get_permiso_requerido()):
            raise PermissionDenied(MENSAJE_ACCESO_DENEGADO)
        self.usuario_cpos = usuario
        return super().dispatch(request, *args, **kwargs)
