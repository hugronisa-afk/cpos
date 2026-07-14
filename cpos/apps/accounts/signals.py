"""Auditoría de eventos de autenticación emitidos por Django."""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db import DatabaseError
from django.dispatch import receiver

from .models import UsuarioCPOS
from .services import registrar_bitacora


def _registrar_evento_sin_interrumpir(**datos):
    """La indisponibilidad de auditoría no debe exponer errores del login."""
    try:
        registrar_bitacora(**datos)
    except DatabaseError:
        # El error de infraestructura debe registrarse en el sistema de logs de
        # despliegue, pero nunca sustituir el mensaje genérico de credenciales.
        return None
    return True


@receiver(
    user_logged_in,
    dispatch_uid="accounts_bitacora_inicio_sesion_exitoso",
)
def registrar_inicio_sesion(sender, request, user, **kwargs):
    if not isinstance(user, UsuarioCPOS):
        return
    _registrar_evento_sin_interrumpir(
        usuario=user,
        modulo="seguridad",
        accion="inicio_sesion_exitoso",
        tabla_afectada="usuarios",
        registro_id=user.pk,
        descripcion="Inicio de sesión exitoso.",
        request=request,
    )


@receiver(
    user_login_failed,
    dispatch_uid="accounts_bitacora_inicio_sesion_fallido",
)
def registrar_intento_fallido(sender, credentials, request, **kwargs):
    # No se usa ni se registra el contenido de credentials. Django ya limpia
    # campos sensibles antes de emitir la señal, pero aquí se ignoran por completo.
    _registrar_evento_sin_interrumpir(
        usuario=None,
        modulo="seguridad",
        accion="inicio_sesion_fallido",
        tabla_afectada="usuarios",
        descripcion="Intento de inicio de sesión fallido.",
        request=request,
    )


@receiver(
    user_logged_out,
    dispatch_uid="accounts_bitacora_cierre_sesion",
)
def registrar_cierre_sesion(sender, request, user, **kwargs):
    if not isinstance(user, UsuarioCPOS):
        return
    _registrar_evento_sin_interrumpir(
        usuario=user,
        modulo="seguridad",
        accion="cierre_sesion",
        tabla_afectada="usuarios",
        registro_id=user.pk,
        descripcion="Cierre de sesión.",
        request=request,
    )
