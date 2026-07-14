"""Backend tradicional de autenticación para la tabla ``cpos.usuarios``."""

import secrets

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password, make_password

from .models import UsuarioCPOS
from .services import verificar_usuario_activo


# Un hash válido y aleatorio evita que un usuario inexistente responda mucho más
# rápido que uno existente. Nunca se almacena ni se utiliza como credencial.
_HASH_COMPARACION = make_password(secrets.token_urlsafe(32))


class UsuarioCPOSBackend(BaseBackend):
    """Autentica exclusivamente con ``nombre_usuario`` y contraseña Django."""

    def authenticate(
        self,
        request,
        username=None,
        password=None,
        nombre_usuario=None,
        **kwargs,
    ):
        identificador = nombre_usuario or username
        if not identificador or password is None:
            return None

        identificador = str(identificador).strip().upper()
        try:
            usuario = UsuarioCPOS.objects.select_related("rol").get(
                nombre_usuario__iexact=identificador
            )
        except UsuarioCPOS.DoesNotExist:
            check_password(password, _HASH_COMPARACION)
            return None

        if not self.user_can_authenticate(usuario):
            # Mantiene un coste de verificación comparable incluso para cuentas
            # inactivas o bloqueadas y no revela su estado al formulario.
            usuario.check_password(password)
            return None

        if usuario.check_password(password):
            return usuario
        return None

    def get_user(self, user_id):
        try:
            usuario = UsuarioCPOS.objects.select_related("rol").get(pk=user_id)
        except (UsuarioCPOS.DoesNotExist, TypeError, ValueError):
            return None
        return usuario if self.user_can_authenticate(usuario) else None

    def user_can_authenticate(self, usuario):
        return verificar_usuario_activo(usuario)
