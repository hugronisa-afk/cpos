from django.conf import settings
from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.db import models
from django.db.models.functions import Now
from django.utils.crypto import salted_hmac


class NivelAutoridad(models.TextChoices):
    OPERATIVO = "operativo", "Operativo"
    GESTION = "gestion", "Gestión"
    SUPERVISION = "supervision", "Supervisión"


class EstadoUsuario(models.TextChoices):
    ACTIVO = "activo", "Activo"
    INACTIVO = "inactivo", "Inactivo"
    BLOQUEADO = "bloqueado", "Bloqueado"


class EstadoPrograma(models.TextChoices):
    ACTIVO = "activo", "Activo"
    INACTIVO = "inactivo", "Inactivo"


class EstadoCohorte(models.TextChoices):
    ACTIVA = "activa", "Activa"
    CERRADA = "cerrada", "Cerrada"
    INACTIVA = "inactiva", "Inactiva"


class EstadoTitulacion(models.TextChoices):
    SIN_PROYECTO = "sin_proyecto", "Sin proyecto"
    PROYECTO_BORRADOR = "proyecto_borrador", "Proyecto en borrador"
    EN_REVISION = "en_revision", "En revisión"
    PROYECTO_APROBADO = "proyecto_aprobado", "Proyecto aprobado"
    TUTOR_ASIGNADO = "tutor_asignado", "Tutor asignado"
    EN_TUTORIAS = "en_tutorias", "En tutorías"
    EN_EVIDENCIAS = "en_evidencias", "En evidencias"
    ARTICULO_EN_PROCESO = "articulo_en_proceso", "Artículo en proceso"
    FINALIZADO = "finalizado", "Finalizado"
    RETIRADO = "retirado", "Retirado"


class Rol(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    nivel_autoridad = models.CharField(
        max_length=20,
        choices=NivelAutoridad.choices,
    )
    esta_activo = models.BooleanField(db_default=True)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "roles"
        ordering = ("nombre",)
        verbose_name = "rol"
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre_visible

    @property
    def nombre_visible(self):
        return self.nombre.replace("_", " ").strip().title()


class Permiso(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=150)
    modulo = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True, null=True)
    esta_activo = models.BooleanField(db_default=True)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "permisos"
        ordering = ("modulo", "codigo")
        verbose_name = "permiso"
        verbose_name_plural = "permisos"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class RolPermiso(models.Model):
    id = models.BigAutoField(primary_key=True)
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column="rol_id",
        related_name="asignaciones_permisos",
    )
    permiso = models.ForeignKey(
        Permiso,
        on_delete=models.PROTECT,
        db_column="permiso_id",
        related_name="asignaciones_roles",
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "rol_permiso"
        ordering = ("rol__nombre", "permiso__codigo")
        constraints = (
            models.UniqueConstraint(
                fields=("rol", "permiso"),
                name="uq_rol_permiso",
            ),
        )
        verbose_name = "permiso de rol"
        verbose_name_plural = "permisos de roles"

    def __str__(self):
        return f"{self.rol} - {self.permiso.codigo}"


class UsuarioCPOS(models.Model):
    """Usuario institucional autenticable almacenado en ``cpos.usuarios``."""

    USERNAME_FIELD = "nombre_usuario"
    REQUIRED_FIELDS = ("cedula", "correo", "rol")

    id = models.BigAutoField(primary_key=True)
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column="rol_id",
        related_name="usuarios_cpos",
    )
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    cedula = models.CharField(max_length=20)
    correo = models.EmailField(max_length=180, unique=True)
    contrasena_hash = models.TextField(editable=False)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoUsuario.choices,
        db_default=EstadoUsuario.ACTIVO,
    )
    last_login = models.DateTimeField(
        db_column="ultimo_acceso",
        blank=True,
        null=True,
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())
    nombre_usuario = models.CharField(max_length=30, unique=True)

    class Meta:
        managed = False
        db_table = "usuarios"
        ordering = ("apellidos", "nombres", "nombre_usuario")
        constraints = (
            models.UniqueConstraint(
                fields=("cedula", "rol"),
                name="uq_usuarios_cedula_rol",
            ),
        )
        verbose_name = "usuario CPOS"
        verbose_name_plural = "usuarios CPOS"

    def __str__(self):
        return f"{self.nombre_completo} ({self.nombre_usuario})"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    @property
    def username(self):
        return self.nombre_usuario

    @property
    def email(self):
        return self.correo

    @property
    def first_name(self):
        return self.nombres

    @property
    def last_name(self):
        return self.apellidos

    @property
    def ultimo_acceso(self):
        """Alias legible para la columna usada por ``last_login`` de Django."""
        return self.last_login

    @ultimo_acceso.setter
    def ultimo_acceso(self, value):
        self.last_login = value

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return self.estado == EstadoUsuario.ACTIVO

    @property
    def is_staff(self):
        """El admin estándar permanece deshabilitado hasta su fase específica."""
        return False

    @property
    def is_superuser(self):
        return False

    @property
    def esta_bloqueado(self):
        return self.estado == EstadoUsuario.BLOQUEADO

    def get_username(self):
        return self.nombre_usuario

    def get_full_name(self):
        return self.nombre_completo

    def get_short_name(self):
        return self.nombres

    def set_password(self, raw_password):
        self.contrasena_hash = make_password(raw_password)

    def set_unusable_password(self):
        self.contrasena_hash = make_password(None)

    def has_usable_password(self):
        return is_password_usable(self.contrasena_hash)

    def check_password(self, raw_password):
        return check_password(raw_password, self.contrasena_hash)

    def get_session_auth_hash(self):
        return self._get_session_auth_hash()

    def get_session_auth_fallback_hash(self):
        for fallback_secret in settings.SECRET_KEY_FALLBACKS:
            yield self._get_session_auth_hash(secret=fallback_secret)

    def _get_session_auth_hash(self, secret=None):
        return salted_hmac(
            "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash",
            self.contrasena_hash,
            secret=secret,
            algorithm="sha256",
        ).hexdigest()


class Programa(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    coordinador = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="coordinador_id",
        blank=True,
        null=True,
        related_name="programas_coordinados",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoPrograma.choices,
        db_default=EstadoPrograma.ACTIVO,
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "programas"
        ordering = ("nombre",)
        verbose_name = "programa"
        verbose_name_plural = "programas"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Cohorte(models.Model):
    id = models.BigAutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        db_column="programa_id",
        related_name="cohortes",
    )
    nombre = models.CharField(max_length=150)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=EstadoCohorte.choices,
        db_default=EstadoCohorte.ACTIVA,
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "cohortes"
        ordering = ("-fecha_inicio", "programa__nombre", "nombre")
        constraints = (
            models.UniqueConstraint(
                fields=("programa", "nombre"),
                name="uq_cohortes_programa_nombre",
            ),
        )
        verbose_name = "cohorte"
        verbose_name_plural = "cohortes"

    def __str__(self):
        return f"{self.programa.codigo} - {self.nombre}"


class Maestrante(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.OneToOneField(
        UsuarioCPOS,
        on_delete=models.PROTECT,
        db_column="usuario_id",
        related_name="perfil_maestrante",
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        db_column="programa_id",
        related_name="maestrantes",
    )
    cohorte = models.ForeignKey(
        Cohorte,
        on_delete=models.PROTECT,
        db_column="cohorte_id",
        related_name="maestrantes",
    )
    codigo_matricula = models.CharField(max_length=50, unique=True)
    estado_titulacion = models.CharField(
        max_length=40,
        choices=EstadoTitulacion.choices,
        db_default=EstadoTitulacion.SIN_PROYECTO,
    )
    modulo_actual = models.PositiveSmallIntegerField(
        db_default=5,
        help_text="Módulo académico actual del maestrante (elegibilidad de onboarding a partir del módulo 5).",
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "maestrantes"
        ordering = ("usuario__apellidos", "usuario__nombres")
        verbose_name = "maestrante"
        verbose_name_plural = "maestrantes"

    def __str__(self):
        return f"{self.codigo_matricula} - {self.usuario.nombre_completo}"


class Bitacora(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="usuario_id",
        blank=True,
        null=True,
        related_name="registros_bitacora",
    )
    modulo = models.CharField(max_length=80)
    accion = models.CharField(max_length=120)
    tabla_afectada = models.CharField(max_length=120, blank=True, null=True)
    registro_id = models.BigIntegerField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    direccion_ip = models.GenericIPAddressField(blank=True, null=True)
    agente_usuario = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "bitacora"
        ordering = ("-fecha_creacion", "-id")
        verbose_name = "registro de bitácora"
        verbose_name_plural = "registros de bitácora"

    def __str__(self):
        return f"{self.modulo}: {self.accion} ({self.fecha_creacion})"
