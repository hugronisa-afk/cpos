from django.db import models
from django.utils import timezone


# ============================================================
# CHOICES GENERALES
# ============================================================

ESTADO_GENERAL_CHOICES = [
    ("activo", "Activo"),
    ("inactivo", "Inactivo"),
]

ESTADO_TUTORIA_CHOICES = [
    ("programada", "Programada"),
    ("realizada", "Realizada"),
    ("no_realizada", "No realizada"),
    ("reprogramada", "Reprogramada"),
    ("cancelada", "Cancelada"),
]

TIPO_EVIDENCIA_CHOICES = [
    ("busqueda_bibliografica", "Búsqueda bibliográfica"),
    ("titulo", "Título"),
    ("introduccion", "Introducción"),
    ("metodologia", "Metodología"),
    ("resultados", "Resultados"),
    ("conclusiones", "Conclusiones"),
    ("referencias", "Referencias"),
    ("otro", "Otro"),
]

ESTADO_EVIDENCIA_CHOICES = [
    ("pendiente", "Pendiente"),
    ("en_revision", "En revisión"),
    ("validada", "Validada"),
    ("observada", "Observada"),
    ("rechazada", "Rechazada"),
]

TIPO_PARTICIPANTE_CHOICES = [
    ("maestrante", "Maestrante"),
    ("tutor", "Tutor"),
]

ESTADO_APROBACION_CHOICES = [
    ("pendiente", "Pendiente"),
    ("aprobada", "Aprobada"),
    ("rechazada", "Rechazada"),
    ("observada", "Observada"),
]

SECCION_ARTICULO_CHOICES = [
    ("titulo", "Título"),
    ("introduccion", "Introducción"),
    ("metodologia", "Metodología"),
    ("resultados", "Resultados"),
    ("conclusiones", "Conclusiones"),
    ("referencias", "Referencias"),
]


# ============================================================
# MODELOS BASE DE ACCOUNTS / PERSONA 1
# managed = False porque las tablas ya existen en Supabase.
# ============================================================

class Rol(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_GENERAL_CHOICES,
        default="activo",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "roles"
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.nombre or f"Rol {self.id}"


class Usuario(models.Model):
    id = models.BigAutoField(primary_key=True)
    rol = models.ForeignKey(
        Rol,
        on_delete=models.DO_NOTHING,
        db_column="rol_id",
        blank=True,
        null=True,
        related_name="usuarios",
    )
    nombres = models.CharField(max_length=150, blank=True, null=True)
    apellidos = models.CharField(max_length=150, blank=True, null=True)
    cedula = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=150, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_GENERAL_CHOICES,
        default="activo",
        blank=True,
        null=True,
    )
    ultimo_acceso = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "usuarios"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        nombre = f"{self.nombres or ''} {self.apellidos or ''}".strip()
        return nombre or self.email or f"Usuario {self.id}"


class Programa(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_GENERAL_CHOICES,
        default="activo",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "programas"
        verbose_name = "Programa"
        verbose_name_plural = "Programas"

    def __str__(self):
        return self.nombre or f"Programa {self.id}"


class Cohorte(models.Model):
    id = models.BigAutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa,
        on_delete=models.DO_NOTHING,
        db_column="programa_id",
        blank=True,
        null=True,
        related_name="cohortes",
    )
    nombre = models.CharField(max_length=100)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_GENERAL_CHOICES,
        default="activo",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "cohortes"
        verbose_name = "Cohorte"
        verbose_name_plural = "Cohortes"

    def __str__(self):
        return self.nombre or f"Cohorte {self.id}"


class Maestrante(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="usuario_id",
        blank=True,
        null=True,
        related_name="maestrantes",
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.DO_NOTHING,
        db_column="programa_id",
        blank=True,
        null=True,
        related_name="maestrantes",
    )
    cohorte = models.ForeignKey(
        Cohorte,
        on_delete=models.DO_NOTHING,
        db_column="cohorte_id",
        blank=True,
        null=True,
        related_name="maestrantes",
    )
    codigo_matricula = models.CharField(max_length=50, blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        default="activo",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "maestrantes"
        verbose_name = "Maestrante"
        verbose_name_plural = "Maestrantes"

    def __str__(self):
        if self.usuario:
            return str(self.usuario)
        return f"Maestrante {self.id}"


class Bitacora(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="usuario_id",
        blank=True,
        null=True,
        related_name="acciones_bitacora",
    )
    accion = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    tabla_afectada = models.CharField(max_length=100, blank=True, null=True)
    registro_id = models.BigIntegerField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "bitacora"
        verbose_name = "Bitácora"
        verbose_name_plural = "Bitácora"

    def __str__(self):
        return f"{self.accion} - {self.fecha}"


# ============================================================
# MODELOS DE TITULACIÓN / PERSONA 2
# También managed = False.
# ============================================================

class Tutor(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="usuario_id",
        blank=True,
        null=True,
        related_name="tutores",
    )
    especialidad = models.CharField(max_length=200, blank=True, null=True)
    area_conocimiento = models.CharField(max_length=200, blank=True, null=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_GENERAL_CHOICES,
        default="activo",
        blank=True,
        null=True,
    )
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "tutores"
        verbose_name = "Tutor"
        verbose_name_plural = "Tutores"

    def __str__(self):
        if self.usuario:
            return str(self.usuario)
        return f"Tutor {self.id}"


class ProyectoTitulacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    maestrante = models.ForeignKey(
        Maestrante,
        on_delete=models.DO_NOTHING,
        db_column="maestrante_id",
        blank=True,
        null=True,
        related_name="proyectos",
    )
    titulo = models.TextField(blank=True, null=True)
    modalidad = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=50, blank=True, null=True)
    numero_resolucion = models.CharField(max_length=100, blank=True, null=True)
    fecha_resolucion = models.DateField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "proyectos_titulacion"
        verbose_name = "Proyecto de titulación"
        verbose_name_plural = "Proyectos de titulación"

    def __str__(self):
        return self.titulo or f"Proyecto {self.id}"


class AsignacionTutor(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="asignaciones_tutor",
    )
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.DO_NOTHING,
        db_column="tutor_id",
        blank=True,
        null=True,
        related_name="asignaciones",
    )
    fecha_asignacion = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=30, default="activo", blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "asignaciones_tutor"
        verbose_name = "Asignación de tutor"
        verbose_name_plural = "Asignaciones de tutor"

    def __str__(self):
        return f"Asignación {self.id}"


# ============================================================
# MODELOS PROPIOS DEL SEGUIMIENTO
# ============================================================

class Tutoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="tutorias",
    )
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.DO_NOTHING,
        db_column="tutor_id",
        blank=True,
        null=True,
        related_name="tutorias",
    )
    numero = models.PositiveSmallIntegerField(blank=True, null=True)
    tema = models.CharField(max_length=255, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    hora_inicio = models.TimeField(blank=True, null=True)
    hora_fin = models.TimeField(blank=True, null=True)
    enlace_sala = models.URLField(max_length=500, blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_TUTORIA_CHOICES,
        default="programada",
        blank=True,
        null=True,
    )
    observaciones = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "tutorias"
        verbose_name = "Tutoría"
        verbose_name_plural = "Tutorías"
        ordering = ["fecha", "hora_inicio", "numero"]

    def __str__(self):
        return f"Tutoría {self.numero or self.id} - {self.tema or 'Sin tema'}"


class AsistenciaTutoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.DO_NOTHING,
        db_column="tutoria_id",
        blank=True,
        null=True,
        related_name="asistencias",
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="usuario_id",
        blank=True,
        null=True,
        related_name="asistencias_tutoria",
    )
    tipo_participante = models.CharField(
        max_length=30,
        choices=TIPO_PARTICIPANTE_CHOICES,
        blank=True,
        null=True,
    )
    asistio = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)
    registrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="registrado_por_id",
        blank=True,
        null=True,
        related_name="asistencias_registradas",
    )
    fecha_registro = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "asistencias_tutoria"
        verbose_name = "Asistencia a tutoría"
        verbose_name_plural = "Asistencias a tutoría"

    def __str__(self):
        return f"Asistencia tutoría {self.tutoria_id} - {self.tipo_participante}"


class ReprogramacionTutoria(models.Model):
    id = models.BigAutoField(primary_key=True)
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.DO_NOTHING,
        db_column="tutoria_id",
        blank=True,
        null=True,
        related_name="reprogramaciones",
    )
    fecha_anterior = models.DateField(blank=True, null=True)
    hora_inicio_anterior = models.TimeField(blank=True, null=True)
    hora_fin_anterior = models.TimeField(blank=True, null=True)
    fecha_nueva = models.DateField(blank=True, null=True)
    hora_inicio_nueva = models.TimeField(blank=True, null=True)
    hora_fin_nueva = models.TimeField(blank=True, null=True)
    motivo = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_APROBACION_CHOICES,
        default="pendiente",
        blank=True,
        null=True,
    )
    solicitado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="reprogramaciones_solicitadas",
    )
    aprobado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="aprobado_por_id",
        blank=True,
        null=True,
        related_name="reprogramaciones_aprobadas",
    )
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "reprogramaciones_tutoria"
        verbose_name = "Reprogramación de tutoría"
        verbose_name_plural = "Reprogramaciones de tutoría"

    def __str__(self):
        return f"Reprogramación tutoría {self.tutoria_id}"


class Grabacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="grabaciones",
    )
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.DO_NOTHING,
        db_column="tutoria_id",
        blank=True,
        null=True,
        related_name="grabaciones",
    )
    enlace = models.URLField(max_length=500, blank=True, null=True)
    archivo = models.FileField(upload_to="grabaciones/", blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    registrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="registrado_por_id",
        blank=True,
        null=True,
        related_name="grabaciones_registradas",
    )
    fecha_registro = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "grabaciones"
        verbose_name = "Grabación"
        verbose_name_plural = "Grabaciones"

    def __str__(self):
        return f"Grabación tutoría {self.tutoria_id}"


class Evidencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="evidencias",
    )
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.DO_NOTHING,
        db_column="tutoria_id",
        blank=True,
        null=True,
        related_name="evidencias",
    )
    tipo_avance = models.CharField(
        max_length=50,
        choices=TIPO_EVIDENCIA_CHOICES,
        blank=True,
        null=True,
    )
    titulo = models.CharField(max_length=255, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    archivo = models.FileField(upload_to="evidencias/", blank=True, null=True)
    enlace = models.URLField(max_length=500, blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_EVIDENCIA_CHOICES,
        default="pendiente",
        blank=True,
        null=True,
    )
    cargado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="cargado_por_id",
        blank=True,
        null=True,
        related_name="evidencias_cargadas",
    )
    fecha_carga = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "evidencias"
        verbose_name = "Evidencia"
        verbose_name_plural = "Evidencias"
        ordering = ["-fecha_carga", "-id"]

    def __str__(self):
        return self.titulo or f"Evidencia {self.id}"

    def clean(self):
        """
        Regla importante:
        La evidencia debe pertenecer al mismo proyecto de la tutoría.
        """
        from django.core.exceptions import ValidationError

        if self.tutoria and self.proyecto:
            if self.tutoria.proyecto_id != self.proyecto_id:
                raise ValidationError(
                    "La evidencia no puede asociarse a una tutoría de otro proyecto."
                )


class EvidenciaVersion(models.Model):
    id = models.BigAutoField(primary_key=True)
    evidencia = models.ForeignKey(
        Evidencia,
        on_delete=models.DO_NOTHING,
        db_column="evidencia_id",
        blank=True,
        null=True,
        related_name="versiones",
    )
    numero_version = models.PositiveIntegerField(blank=True, null=True)
    archivo = models.FileField(upload_to="evidencias/versiones/", blank=True, null=True)
    enlace = models.URLField(max_length=500, blank=True, null=True)
    descripcion_cambios = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="creado_por_id",
        blank=True,
        null=True,
        related_name="versiones_evidencia_creadas",
    )
    creado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "evidencia_versiones"
        verbose_name = "Versión de evidencia"
        verbose_name_plural = "Versiones de evidencias"
        ordering = ["-numero_version", "-id"]

    def __str__(self):
        return f"Evidencia {self.evidencia_id} - Versión {self.numero_version}"


class ValidacionEvidencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    evidencia = models.ForeignKey(
        Evidencia,
        on_delete=models.DO_NOTHING,
        db_column="evidencia_id",
        blank=True,
        null=True,
        related_name="validaciones",
    )
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.DO_NOTHING,
        db_column="tutor_id",
        blank=True,
        null=True,
        related_name="validaciones_evidencia",
    )
    validado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="validado_por_id",
        blank=True,
        null=True,
        related_name="validaciones_realizadas",
    )
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_EVIDENCIA_CHOICES,
        blank=True,
        null=True,
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_validacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "validaciones_evidencia"
        verbose_name = "Validación de evidencia"
        verbose_name_plural = "Validaciones de evidencia"
        ordering = ["-fecha_validacion", "-id"]

    def __str__(self):
        return f"Validación evidencia {self.evidencia_id} - {self.estado}"


# ============================================================
# ARTÍCULO CIENTÍFICO
# Si tu tabla articulos ya existe, también va managed = False.
# ============================================================

class Articulo(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="articulos",
    )
    titulo = models.TextField(blank=True, null=True)
    introduccion = models.TextField(blank=True, null=True)
    metodologia = models.TextField(blank=True, null=True)
    resultados = models.TextField(blank=True, null=True)
    conclusiones = models.TextField(blank=True, null=True)
    referencias = models.TextField(blank=True, null=True)

    revista_nombre = models.CharField(max_length=255, blank=True, null=True)
    revista_url = models.URLField(max_length=500, blank=True, null=True)
    fecha_envio_revista = models.DateField(blank=True, null=True)
    estado_respuesta_revista = models.CharField(max_length=100, blank=True, null=True)
    observaciones_revista = models.TextField(blank=True, null=True)

    estado = models.CharField(max_length=50, blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "articulos"
        verbose_name = "Artículo científico"
        verbose_name_plural = "Artículos científicos"

    def __str__(self):
        return self.titulo or f"Artículo {self.id}"


# ============================================================
# APROBACIONES Y CAMBIOS
# ============================================================

class Aprobacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="aprobaciones",
    )
    tipo = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_APROBACION_CHOICES,
        default="pendiente",
        blank=True,
        null=True,
    )
    observaciones = models.TextField(blank=True, null=True)
    solicitado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="aprobaciones_solicitadas",
    )
    aprobado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="aprobado_por_id",
        blank=True,
        null=True,
        related_name="aprobaciones_realizadas",
    )
    fecha_solicitud = models.DateTimeField(blank=True, null=True)
    fecha_respuesta = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "aprobaciones"
        verbose_name = "Aprobación"
        verbose_name_plural = "Aprobaciones"

    def __str__(self):
        return f"{self.tipo} - {self.estado}"


class SolicitudCambioTema(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.DO_NOTHING,
        db_column="proyecto_id",
        blank=True,
        null=True,
        related_name="solicitudes_cambio_tema",
    )
    tema_anterior = models.TextField(blank=True, null=True)
    tema_propuesto = models.TextField(blank=True, null=True)
    justificacion = models.TextField(blank=True, null=True)
    documento_respaldo = models.FileField(
        upload_to="solicitudes_cambio_tema/",
        blank=True,
        null=True,
    )
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_APROBACION_CHOICES,
        default="pendiente",
        blank=True,
        null=True,
    )
    solicitado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="cambios_tema_solicitados",
    )
    revisado_por = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="revisado_por_id",
        blank=True,
        null=True,
        related_name="cambios_tema_revisados",
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_solicitud = models.DateTimeField(blank=True, null=True)
    fecha_respuesta = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "solicitudes_cambio_tema"
        verbose_name = "Solicitud de cambio de tema"
        verbose_name_plural = "Solicitudes de cambio de tema"

    def __str__(self):
        return f"Cambio de tema {self.id} - {self.estado}"


# ============================================================
# NOTIFICACIONES
# ============================================================

class Notificacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.DO_NOTHING,
        db_column="usuario_id",
        blank=True,
        null=True,
        related_name="notificaciones",
    )
    titulo = models.CharField(max_length=200, blank=True, null=True)
    mensaje = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    leida = models.BooleanField(default=False)
    url_destino = models.CharField(max_length=500, blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "notificaciones"
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ["-creado_en", "-id"]

    def __str__(self):
        return self.titulo or f"Notificación {self.id}"