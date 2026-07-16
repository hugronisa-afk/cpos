from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Now
from django.utils import timezone

from apps.accounts.models import Maestrante, Programa, UsuarioCPOS


class EstadoTutor(models.TextChoices):
    DISPONIBLE = "disponible", "Disponible"
    NO_DISPONIBLE = "no_disponible", "No disponible"
    INACTIVO = "inactivo", "Inactivo"


class ModalidadProyecto(models.TextChoices):
    ARTICULO = "articulo_cientifico", "Artículo científico"
    INVESTIGACION = "proyecto_investigacion", "Proyecto de investigación"
    EXAMEN = "examen_complexivo", "Examen complexivo"
    OTRA = "otra", "Otra"


class EstadoProyecto(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    EN_REVISION = "en_revision", "En revisión"
    OBSERVADO = "observado", "Observado"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    CERRADO = "cerrado", "Cerrado"


class EstadoAsignacion(models.TextChoices):
    ACTIVO = "activo", "Activa"
    REEMPLAZADO = "reemplazado", "Reemplazada"
    FINALIZADO = "finalizado", "Finalizada"


class EstadoTutoria(models.TextChoices):
    PROGRAMADA = "programada", "Programada"
    REALIZADA = "realizada", "Realizada"
    NO_REALIZADA = "no_realizada", "No realizada"
    REPROGRAMADA = "reprogramada", "Reprogramada"
    CANCELADA = "cancelada", "Cancelada"


class EstadoReprogramacion(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"


class EstadoSolicitudCambioTutor(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"
    CANCELADA = "cancelada", "Cancelada"


class DiaSemana(models.IntegerChoices):
    LUNES = 0, "Lunes"
    MARTES = 1, "Martes"
    MIERCOLES = 2, "Miércoles"
    JUEVES = 3, "Jueves"
    VIERNES = 4, "Viernes"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class TipoArchivo(models.TextChoices):
    WORD = "word", "Documento Word"
    PDF = "pdf", "Documento PDF"
    RESOLUCION = "resolucion", "Resolución"
    ANEXO = "anexo", "Anexo"


class TipoGrabacion(models.TextChoices):
    ENLACE = "enlace", "Enlace"
    ARCHIVO = "archivo", "Archivo"


class EstadoArticulo(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    EN_REVISION = "en_revision", "En revisión"
    COMPLETO = "completo", "Completo"
    ENVIADO = "enviado_revista", "Enviado a revista"
    ACEPTADO = "aceptado", "Aceptado"
    RECHAZADO = "rechazado", "Rechazado"


class EstadoCambioTema(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    EN_REVISION = "en_revision", "En revisión"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"


class EstadoCambioModalidad(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"


class TipoAprobacion(models.TextChoices):
    PROYECTO = "proyecto", "Proyecto"
    CAMBIO_TEMA = "cambio_tema", "Cambio de tema"
    CAMBIO_TUTOR = "cambio_tutor", "Cambio de tutor"
    REPROGRAMACION = "reprogramacion", "Reprogramación"
    CIERRE = "cierre_proceso", "Cierre de proceso"
    ARTICULO = "articulo", "Artículo"
    ARCHIVO_PROYECTO = "archivo_proyecto", "Archivo de proyecto"
    CAMBIO_MODALIDAD = "cambio_modalidad", "Cambio de modalidad"


class EstadoAprobacion(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    OBSERVADO = "observado", "Observado"


class TipoProcesoAprobacion(models.TextChoices):
    PROYECTO = "proyecto", "Aprobación de proyecto"
    CAMBIO_TEMA = "cambio_tema", "Cambio de tema"
    CAMBIO_MODALIDAD = "cambio_modalidad", "Cambio de modalidad"


class EstadoProcesoAprobacion(models.TextChoices):
    EN_CURSO = "en_curso", "En curso"
    OBSERVADO = "observado", "Observado"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    CANCELADO = "cancelado", "Cancelado"


class EstadoPasoAprobacion(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    ACTIVO = "activo", "En revisión"
    APROBADO = "aprobado", "Aprobado"
    OBSERVADO = "observado", "Observado"
    RECHAZADO = "rechazado", "Rechazado"


class EstadoOnboarding(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    EN_SELECCION = "en_seleccion", "En selección"
    COMPLETADO = "completado", "Completado"
    BLOQUEADO = "bloqueado", "Bloqueado"
    REQUIERE_CORRECCION = "requiere_correccion", "Requiere corrección"


class EstadoEtapaProducto(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    ENVIADA = "enviada", "Enviada"
    EN_REVISION = "en_revision", "En revisión"
    OBSERVADA = "observada", "Observada"
    APROBADA = "aprobada", "Aprobada"
    RECHAZADA = "rechazada", "Rechazada"


class ResultadoExamenComplexivo(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    APROBADO = "aprobado", "Aprobado"
    REPROBADO = "reprobado", "Reprobado"
    NO_SE_PRESENTO = "no_se_presento", "No se presentó"


class TipoDocumentoAprobacion(models.TextChoices):
    WORD = "word", "Documento editable Word"
    PDF = "pdf", "Documento PDF"
    RESPALDO = "respaldo", "Documento de respaldo"
    RESOLUCION = "resolucion", "Resolución oficial"


class ActualizacionMixin(models.Model):
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.fecha_actualizacion = timezone.now()
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "fecha_actualizacion"
            }
        return super().save(*args, **kwargs)


class ConfiguracionModalidadPrograma(ActualizacionMixin):
    """Configuración de la opción adicional «Otra» para cada programa."""

    id = models.BigAutoField(primary_key=True)
    programa = models.OneToOneField(
        Programa,
        on_delete=models.PROTECT,
        db_column="programa_id",
        related_name="configuracion_modalidad_otra",
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    tipos_evidencia = models.JSONField(db_default=list)
    producto_final_nombre = models.CharField(max_length=150)
    tipo_archivo_final = models.CharField(
        max_length=30,
        choices=TipoArchivo.choices,
        db_default=TipoArchivo.PDF,
    )
    esta_activa = models.BooleanField(db_default=True)
    creado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="creado_por_id",
        blank=True,
        null=True,
        related_name="configuraciones_modalidad_creadas",
    )
    actualizado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="actualizado_por_id",
        blank=True,
        null=True,
        related_name="configuraciones_modalidad_actualizadas",
    )

    class Meta:
        managed = False
        db_table = "configuraciones_modalidad_programa"
        ordering = ("programa__nombre",)

    def __str__(self):
        return f"{self.programa}: {self.nombre}"

    def clean(self):
        if not str(self.nombre or "").strip():
            raise ValidationError({"nombre": "El nombre de la modalidad es obligatorio."})
        if not str(self.descripcion or "").strip():
            raise ValidationError({"descripcion": "Describa la modalidad y su alcance."})
        if not isinstance(self.tipos_evidencia, list) or not self.tipos_evidencia:
            raise ValidationError(
                {"tipos_evidencia": "Seleccione al menos un tipo de evidencia."}
            )


class Tutor(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    usuario = models.OneToOneField(
        UsuarioCPOS,
        on_delete=models.PROTECT,
        db_column="usuario_id",
        related_name="perfil_tutor",
    )
    especialidad = models.CharField(max_length=200, blank=True, null=True)
    titulo_academico = models.CharField(max_length=200, blank=True, null=True)
    linea_investigacion = models.CharField(max_length=250, blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=EstadoTutor.choices,
        db_default=EstadoTutor.DISPONIBLE,
    )

    class Meta:
        managed = False
        db_table = "tutores"
        ordering = ("usuario__apellidos", "usuario__nombres")

    def __str__(self):
        return self.usuario.nombre_completo


class TutorPrograma(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.PROTECT,
        db_column="tutor_id",
        related_name="vinculos_programa",
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        db_column="programa_id",
        related_name="tutores_vinculados",
    )
    cupo_maximo = models.PositiveSmallIntegerField(db_default=5)
    esta_activo = models.BooleanField(db_default=True)

    class Meta:
        managed = False
        db_table = "tutores_programas"
        ordering = ("programa__nombre", "tutor__usuario__apellidos")
        constraints = (
            models.UniqueConstraint(
                fields=("tutor", "programa"),
                name="uq_tutores_programas_tutor_programa",
            ),
        )

    def __str__(self):
        return f"{self.tutor} · {self.programa}"


class DisponibilidadTutor(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.PROTECT,
        db_column="tutor_id",
        related_name="disponibilidades",
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    esta_activa = models.BooleanField(db_default=True)

    class Meta:
        managed = False
        db_table = "disponibilidades_tutor"
        ordering = ("dia_semana", "hora_inicio")
        constraints = (
            models.UniqueConstraint(
                fields=("tutor", "dia_semana", "hora_inicio", "hora_fin"),
                name="uq_disponibilidad_tutor_bloque",
            ),
        )

    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({"hora_fin": "Debe ser posterior a la hora de inicio."})

    def __str__(self):
        return (
            f"{self.tutor} · {self.get_dia_semana_display()} "
            f"{self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"
        )


class ProyectoTitulacion(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    maestrante = models.ForeignKey(
        Maestrante,
        on_delete=models.PROTECT,
        db_column="maestrante_id",
        related_name="proyectos_titulacion",
    )
    tema = models.TextField()
    modalidad = models.CharField(max_length=40, choices=ModalidadProyecto.choices)
    estado = models.CharField(
        max_length=30,
        choices=EstadoProyecto.choices,
        db_default=EstadoProyecto.BORRADOR,
    )
    numero_resolucion = models.CharField(max_length=100, blank=True, null=True)
    documento_resolucion_url = models.TextField(blank=True, null=True)
    fecha_aprobacion = models.DateField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="creado_por_id",
        blank=True,
        null=True,
        related_name="proyectos_creados",
    )
    actualizado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="actualizado_por_id",
        blank=True,
        null=True,
        related_name="proyectos_actualizados",
    )
    esta_activo = models.BooleanField(db_default=True)

    class Meta:
        managed = False
        db_table = "proyectos_titulacion"
        ordering = ("-fecha_actualizacion", "-id")

    def __str__(self):
        return self.tema


class AsignacionTutor(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="asignaciones_tutor",
    )
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.PROTECT,
        db_column="tutor_id",
        related_name="asignaciones",
    )
    fecha_asignacion = models.DateField(db_default=Now())
    asignado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="asignado_por_id",
        blank=True,
        null=True,
        related_name="asignaciones_tutor_realizadas",
    )
    estado = models.CharField(
        max_length=30,
        choices=EstadoAsignacion.choices,
        db_default=EstadoAsignacion.ACTIVO,
    )
    motivo_cambio = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "asignaciones_tutor"
        ordering = ("-fecha_asignacion", "-id")


class SolicitudCambioTutor(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="solicitudes_cambio_tutor",
    )
    asignacion_actual = models.ForeignKey(
        AsignacionTutor,
        on_delete=models.PROTECT,
        db_column="asignacion_actual_id",
        related_name="solicitudes_cambio",
    )
    tutor_propuesto = models.ForeignKey(
        Tutor,
        on_delete=models.PROTECT,
        db_column="tutor_propuesto_id",
        related_name="solicitudes_para_asignacion",
    )
    motivo = models.TextField()
    solicitado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="cambios_tutor_solicitados",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoSolicitudCambioTutor.choices,
        db_default=EstadoSolicitudCambioTutor.PENDIENTE,
    )
    resuelto_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="resuelto_por_id",
        blank=True,
        null=True,
        related_name="cambios_tutor_resueltos",
    )
    observaciones_resolucion = models.TextField(blank=True, null=True)
    fecha_resolucion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "solicitudes_cambio_tutor"
        ordering = ("-fecha_creacion", "-id")

    def clean(self):
        if (
            self.asignacion_actual_id
            and self.tutor_propuesto_id
            and self.asignacion_actual.tutor_id == self.tutor_propuesto_id
        ):
            raise ValidationError(
                {"tutor_propuesto": "Seleccione un tutor diferente al actual."}
            )
        if not str(self.motivo or "").strip():
            raise ValidationError({"motivo": "Explique el motivo del cambio."})


class Tutoria(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="tutorias",
    )
    tutor = models.ForeignKey(
        Tutor,
        on_delete=models.PROTECT,
        db_column="tutor_id",
        related_name="tutorias",
    )
    numero_tutoria = models.PositiveSmallIntegerField()
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    enlace_virtual = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=EstadoTutoria.choices,
        db_default=EstadoTutoria.PROGRAMADA,
    )
    observacion_general = models.TextField(blank=True, null=True)
    programada_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="programada_por_id",
        blank=True,
        null=True,
        related_name="tutorias_programadas",
    )
    es_excepcional = models.BooleanField(
        db_default=False,
        help_text="Marca la novena tutoría autorizada excepcionalmente (ver AutorizacionNovenaTutoria).",
    )

    class Meta:
        managed = False
        db_table = "tutorias"
        ordering = ("-fecha", "-hora_inicio")
        constraints = (
            models.UniqueConstraint(
                fields=("proyecto", "numero_tutoria"),
                name="uq_tutorias_proyecto_numero",
            ),
        )

    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({"hora_fin": "Debe ser posterior a la hora de inicio."})
        if self.numero_tutoria and not 1 <= self.numero_tutoria <= 9:
            raise ValidationError({"numero_tutoria": "Debe estar entre 1 y 9."})
        if self.numero_tutoria == 9:
            tiene_autorizacion = self._tiene_autorizacion_novena()
            if not tiene_autorizacion:
                raise ValidationError(
                    {
                        "numero_tutoria": (
                            "La novena tutoría requiere una AutorizacionNovenaTutoria "
                            "registrada previamente para el proyecto."
                        )
                    }
                )
            self.es_excepcional = True

    def _tiene_autorizacion_novena(self):
        if not self.proyecto_id:
            return False
        consulta = AutorizacionNovenaTutoria.objects.filter(proyecto_id=self.proyecto_id).filter(
            models.Q(tutoria__isnull=True) | models.Q(tutoria_id=self.pk)
        )
        return consulta.exists()


class AsistenciaTutoria(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    tutoria = models.OneToOneField(
        Tutoria,
        on_delete=models.PROTECT,
        db_column="tutoria_id",
        related_name="asistencia",
    )
    asistio_tutor = models.BooleanField(db_default=False)
    asistio_maestrante = models.BooleanField(db_default=False)
    registrado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="registrado_por_id",
        blank=True,
        null=True,
        related_name="asistencias_registradas",
    )
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "asistencias_tutoria"


class AsistenciaTutoriaHistorial(models.Model):
    id = models.BigAutoField(primary_key=True)
    asistencia = models.ForeignKey(
        AsistenciaTutoria,
        on_delete=models.PROTECT,
        db_column="asistencia_id",
        related_name="historial_correcciones",
    )
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.PROTECT,
        db_column="tutoria_id",
        related_name="historial_asistencia",
    )
    asistio_tutor_anterior = models.BooleanField()
    asistio_maestrante_anterior = models.BooleanField()
    estado_tutoria_anterior = models.CharField(max_length=30, choices=EstadoTutoria.choices)
    asistio_tutor_nuevo = models.BooleanField()
    asistio_maestrante_nuevo = models.BooleanField()
    estado_tutoria_nuevo = models.CharField(max_length=30, choices=EstadoTutoria.choices)
    observaciones_anteriores = models.TextField(blank=True, null=True)
    observaciones_nuevas = models.TextField(blank=True, null=True)
    motivo_correccion = models.TextField()
    corregido_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="corregido_por_id",
        blank=True,
        null=True,
        related_name="correcciones_asistencia_realizadas",
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "asistencias_tutoria_historial"
        ordering = ("-fecha_creacion", "-id")


class ReprogramacionTutoria(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.PROTECT,
        db_column="tutoria_id",
        related_name="reprogramaciones",
    )
    fecha_anterior = models.DateField()
    hora_inicio_anterior = models.TimeField()
    hora_fin_anterior = models.TimeField()
    fecha_nueva = models.DateField()
    hora_inicio_nueva = models.TimeField()
    hora_fin_nueva = models.TimeField()
    motivo = models.TextField()
    solicitado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="reprogramaciones_solicitadas",
    )
    aprobado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="aprobado_por_id",
        blank=True,
        null=True,
        related_name="reprogramaciones_resueltas",
    )
    estado = models.CharField(
        max_length=30,
        choices=EstadoReprogramacion.choices,
        db_default=EstadoReprogramacion.PENDIENTE,
    )
    observaciones_resolucion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "reprogramaciones_tutoria"
        ordering = ("-fecha_creacion",)

    def clean(self):
        if self.hora_inicio_nueva and self.hora_fin_nueva and self.hora_fin_nueva <= self.hora_inicio_nueva:
            raise ValidationError({"hora_fin_nueva": "Debe ser posterior a la hora de inicio."})


class ArchivoProyecto(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="archivos",
    )
    tipo_archivo = models.CharField(max_length=30, choices=TipoArchivo.choices)
    nombre_original = models.CharField(max_length=255)
    ruta_archivo = models.TextField()
    extension = models.CharField(max_length=10)
    tamano_bytes = models.BigIntegerField()
    subido_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="subido_por_id",
        blank=True,
        null=True,
        related_name="archivos_proyecto_subidos",
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "archivos_proyecto"
        ordering = ("-fecha_creacion",)


class Grabacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.PROTECT,
        db_column="tutoria_id",
        related_name="grabaciones",
    )
    tipo_grabacion = models.CharField(max_length=20, choices=TipoGrabacion.choices)
    enlace_grabacion = models.TextField(blank=True, null=True)
    ruta_archivo = models.TextField(blank=True, null=True)
    nombre_original = models.CharField(max_length=255, blank=True, null=True)
    extension = models.CharField(max_length=10, blank=True, null=True)
    tamano_bytes = models.BigIntegerField(blank=True, null=True)
    numero_version = models.PositiveIntegerField(db_default=1)
    esta_activa = models.BooleanField(db_default=True)
    reemplaza_grabacion = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        db_column="reemplaza_grabacion_id",
        blank=True,
        null=True,
        related_name="reemplazos",
    )
    registrado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="registrado_por_id",
        blank=True,
        null=True,
        related_name="grabaciones_registradas",
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "grabaciones"
        ordering = ("-esta_activa", "-numero_version", "-fecha_creacion")
        constraints = (
            models.UniqueConstraint(
                fields=("tutoria", "numero_version"),
                name="uq_grabacion_tutoria_version",
            ),
        )

    def clean(self):
        enlace = (self.enlace_grabacion or "").strip()
        ruta = (self.ruta_archivo or "").strip()
        if self.tipo_grabacion == TipoGrabacion.ENLACE and enlace and not enlace.lower().startswith("https://"):
            raise ValidationError("El enlace de grabacion debe usar HTTPS.")
        if self.numero_version is not None and self.numero_version < 1:
            raise ValidationError("La version de grabacion debe ser positiva.")
        if self.tipo_grabacion == TipoGrabacion.ENLACE and (not enlace or ruta):
            raise ValidationError("Para un enlace indique solo el enlace de grabación.")
        if self.tipo_grabacion == TipoGrabacion.ARCHIVO and (not ruta or enlace):
            raise ValidationError("Para un archivo indique solo su ruta de almacenamiento.")


class Articulo(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="articulos",
    )
    titulo = models.TextField(blank=True, null=True)
    introduccion = models.TextField(blank=True, null=True)
    metodologia = models.TextField(blank=True, null=True)
    resultados = models.TextField(blank=True, null=True)
    conclusiones = models.TextField(blank=True, null=True)
    referencias = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=EstadoArticulo.choices,
        db_default=EstadoArticulo.BORRADOR,
    )
    porcentaje_avance = models.DecimalField(max_digits=5, decimal_places=2, db_default=0)
    fecha_envio_revista = models.DateField(blank=True, null=True)
    estado_respuesta_revista = models.CharField(max_length=100, blank=True, null=True)
    esta_activo = models.BooleanField(db_default=True)

    class Meta:
        managed = False
        db_table = "articulos"
        ordering = ("-fecha_actualizacion",)

    def clean(self):
        if self.porcentaje_avance is not None and not 0 <= self.porcentaje_avance <= 100:
            raise ValidationError({"porcentaje_avance": "Debe estar entre 0 y 100."})


class SolicitudCambioTema(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="solicitudes_cambio_tema",
    )
    tema_actual = models.TextField()
    tema_propuesto = models.TextField()
    justificacion = models.TextField()
    solicitado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="cambios_tema_solicitados",
    )
    estado = models.CharField(
        max_length=30,
        choices=EstadoCambioTema.choices,
        db_default=EstadoCambioTema.PENDIENTE,
    )

    class Meta:
        managed = False
        db_table = "solicitudes_cambio_tema"
        ordering = ("-fecha_creacion",)


class SolicitudCambioModalidad(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="solicitudes_cambio_modalidad",
    )
    modalidad_actual = models.CharField(max_length=40, choices=ModalidadProyecto.choices)
    modalidad_propuesta = models.CharField(
        max_length=40,
        choices=ModalidadProyecto.choices,
    )
    justificacion = models.TextField()
    solicitado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="solicitado_por_id",
        blank=True,
        null=True,
        related_name="cambios_modalidad_solicitados",
    )
    estado = models.CharField(
        max_length=30,
        choices=EstadoCambioModalidad.choices,
        db_default=EstadoCambioModalidad.PENDIENTE,
    )
    resuelto_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="resuelto_por_id",
        blank=True,
        null=True,
        related_name="cambios_modalidad_resueltos",
    )
    observaciones_resolucion = models.TextField(blank=True, null=True)
    fecha_resolucion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "solicitudes_cambio_modalidad"
        ordering = ("-fecha_creacion",)

    def clean(self):
        if self.modalidad_actual == self.modalidad_propuesta:
            raise ValidationError(
                {"modalidad_propuesta": "Seleccione una modalidad diferente a la actual."}
            )
        if not str(self.justificacion or "").strip():
            raise ValidationError({"justificacion": "La justificación es obligatoria."})


class Aprobacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="aprobaciones",
    )
    tipo_aprobacion = models.CharField(max_length=30, choices=TipoAprobacion.choices)
    referencia_tabla = models.CharField(max_length=100, blank=True, null=True)
    referencia_id = models.BigIntegerField(blank=True, null=True)
    aprobado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="aprobado_por_id",
        blank=True,
        null=True,
        related_name="aprobaciones_resueltas",
    )
    estado = models.CharField(
        max_length=30,
        choices=EstadoAprobacion.choices,
        db_default=EstadoAprobacion.PENDIENTE,
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "aprobaciones"
        ordering = ("-fecha_creacion",)


class ProcesoAprobacion(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="procesos_aprobacion",
    )
    tipo = models.CharField(max_length=40, choices=TipoProcesoAprobacion.choices)
    referencia_tabla = models.CharField(max_length=100)
    referencia_id = models.BigIntegerField()
    numero_version = models.PositiveSmallIntegerField(db_default=1)
    estado = models.CharField(
        max_length=30,
        choices=EstadoProcesoAprobacion.choices,
        db_default=EstadoProcesoAprobacion.EN_CURSO,
    )
    paso_actual = models.PositiveSmallIntegerField(db_default=1)
    creado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="creado_por_id",
        blank=True,
        null=True,
        related_name="procesos_aprobacion_creados",
    )
    fecha_finalizacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "procesos_aprobacion"
        ordering = ("-fecha_creacion", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=(
                    "tipo",
                    "referencia_tabla",
                    "referencia_id",
                    "numero_version",
                ),
                name="uq_proceso_aprobacion_version",
            ),
        )

    def __str__(self):
        return f"{self.get_tipo_display()} · versión {self.numero_version}"


class PasoAprobacion(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proceso = models.ForeignKey(
        ProcesoAprobacion,
        on_delete=models.PROTECT,
        db_column="proceso_id",
        related_name="pasos",
    )
    orden = models.PositiveSmallIntegerField()
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=150)
    instancia = models.CharField(max_length=150)
    rol_responsable = models.CharField(max_length=50)
    estado = models.CharField(
        max_length=30,
        choices=EstadoPasoAprobacion.choices,
        db_default=EstadoPasoAprobacion.PENDIENTE,
    )
    resuelto_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="resuelto_por_id",
        blank=True,
        null=True,
        related_name="pasos_aprobacion_resueltos",
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_resolucion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "pasos_aprobacion"
        ordering = ("orden", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("proceso", "orden"),
                name="uq_paso_aprobacion_orden",
            ),
            models.UniqueConstraint(
                fields=("proceso", "codigo"),
                name="uq_paso_aprobacion_codigo",
            ),
        )

    def __str__(self):
        return f"{self.proceso} · {self.nombre}"


class DocumentoProcesoAprobacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    proceso = models.ForeignKey(
        ProcesoAprobacion,
        on_delete=models.PROTECT,
        db_column="proceso_id",
        related_name="documentos",
    )
    archivo = models.ForeignKey(
        ArchivoProyecto,
        on_delete=models.PROTECT,
        db_column="archivo_id",
        related_name="usos_en_aprobacion",
    )
    tipo_documento = models.CharField(
        max_length=30,
        choices=TipoDocumentoAprobacion.choices,
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "documentos_proceso_aprobacion"
        ordering = ("tipo_documento", "id")
        constraints = (
            models.UniqueConstraint(
                fields=("proceso", "tipo_documento"),
                name="uq_documento_proceso_tipo",
            ),
        )

    def __str__(self):
        return f"{self.proceso} · {self.get_tipo_documento_display()}"


# ---------------------------------------------------------------------------
# Fase 7A — Onboarding obligatorio del maestrante
# ---------------------------------------------------------------------------


class OnboardingMaestrante(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.OneToOneField(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="onboarding",
    )
    maestrante = models.OneToOneField(
        Maestrante,
        on_delete=models.PROTECT,
        db_column="maestrante_id",
        related_name="onboarding",
    )
    estado = models.CharField(
        max_length=30,
        choices=EstadoOnboarding.choices,
        db_default=EstadoOnboarding.PENDIENTE,
    )
    modalidad_seleccionada = models.CharField(
        max_length=40,
        choices=ModalidadProyecto.choices,
        blank=True,
        null=True,
    )
    fecha_seleccion = models.DateTimeField(blank=True, null=True)
    seleccionado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="seleccionado_por_id",
        blank=True,
        null=True,
        related_name="onboardings_seleccionados",
    )
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "onboarding_maestrantes"
        ordering = ("-fecha_creacion", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("maestrante",),
                name="uq_onboarding_maestrante",
            ),
        )

    def __str__(self):
        return f"Onboarding {self.maestrante} ({self.estado})"

    def clean(self):
        if (
            self.estado == EstadoOnboarding.COMPLETADO
            and not self.modalidad_seleccionada
        ):
            raise ValidationError(
                {"modalidad_seleccionada": "Debe registrarse la modalidad elegida para completar el onboarding."}
            )


# ---------------------------------------------------------------------------
# Fase 7B — Configuración de modalidades editable por supervisor
# ---------------------------------------------------------------------------


class ModalidadConfigurada(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        db_column="programa_id",
        related_name="modalidades_configuradas",
        blank=True,
        null=True,
        help_text="Nulo = configuración global (aplica a todos los programas).",
    )
    tipo_modalidad = models.CharField(max_length=40, choices=ModalidadProyecto.choices)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    requiere_tutor = models.BooleanField(db_default=True)
    esta_activa = models.BooleanField(db_default=True)
    es_semilla_base = models.BooleanField(
        db_default=False,
        help_text="Marca las 3 modalidades base migradas desde REGLAS_BASE.",
    )
    creado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="creado_por_id",
        blank=True,
        null=True,
        related_name="modalidades_configuradas_creadas",
    )
    actualizado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="actualizado_por_id",
        blank=True,
        null=True,
        related_name="modalidades_configuradas_actualizadas",
    )

    class Meta:
        managed = False
        db_table = "modalidades_configuradas"
        ordering = ("programa__nombre", "tipo_modalidad")

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_modalidad_display()})"

    def clean(self):
        if not str(self.nombre or "").strip():
            raise ValidationError({"nombre": "El nombre de la modalidad es obligatorio."})


class EtapaProducto(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    modalidad = models.ForeignKey(
        ModalidadConfigurada,
        on_delete=models.PROTECT,
        db_column="modalidad_id",
        related_name="etapas",
    )
    orden = models.PositiveSmallIntegerField()
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    es_obligatoria = models.BooleanField(db_default=True)
    esta_activa = models.BooleanField(db_default=True)

    class Meta:
        managed = False
        db_table = "etapas_producto"
        ordering = ("modalidad_id", "orden")
        constraints = (
            models.UniqueConstraint(
                fields=("modalidad", "orden"),
                name="uq_etapa_producto_modalidad_orden",
            ),
            models.UniqueConstraint(
                fields=("modalidad", "codigo"),
                name="uq_etapa_producto_modalidad_codigo",
            ),
        )

    def __str__(self):
        return f"{self.modalidad} · {self.nombre}"


class EntregaEtapa(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="entregas_etapa",
    )
    etapa = models.ForeignKey(
        EtapaProducto,
        on_delete=models.PROTECT,
        db_column="etapa_id",
        related_name="entregas",
    )
    numero_version = models.PositiveIntegerField(db_default=1)
    archivo = models.ForeignKey(
        ArchivoProyecto,
        on_delete=models.PROTECT,
        db_column="archivo_id",
        blank=True,
        null=True,
        related_name="entregas_etapa",
    )
    comentario_maestrante = models.TextField(blank=True, null=True)
    estado = models.CharField(
        max_length=30,
        choices=EstadoEtapaProducto.choices,
        db_default=EstadoEtapaProducto.BORRADOR,
    )
    evaluacion = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    coordinador_responsable = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="coordinador_responsable_id",
        blank=True,
        null=True,
        related_name="entregas_etapa_evaluadas",
    )
    fecha_evaluacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "entregas_etapa"
        ordering = ("proyecto_id", "etapa__orden", "-numero_version")
        constraints = (
            models.UniqueConstraint(
                fields=("proyecto", "etapa", "numero_version"),
                name="uq_entrega_etapa_proyecto_etapa_version",
            ),
        )

    def __str__(self):
        return f"{self.proyecto} · {self.etapa} v{self.numero_version}"

    def clean(self):
        if self.numero_version is not None and self.numero_version < 1:
            raise ValidationError({"numero_version": "La versión debe ser positiva."})


# ---------------------------------------------------------------------------
# Fase 7C — Novena tutoría excepcional
# ---------------------------------------------------------------------------


class AutorizacionNovenaTutoria(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="autorizaciones_novena_tutoria",
    )
    tutoria = models.OneToOneField(
        Tutoria,
        on_delete=models.PROTECT,
        db_column="tutoria_id",
        blank=True,
        null=True,
        related_name="autorizacion_novena",
        help_text="Se vincula una vez creada la novena tutoría autorizada.",
    )
    solicitante = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="solicitante_id",
        blank=True,
        null=True,
        related_name="novenas_tutoria_solicitadas",
    )
    motivo = models.TextField()
    autorizado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="autorizado_por_id",
        blank=True,
        null=True,
        related_name="novenas_tutoria_autorizadas",
    )
    fecha_autorizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "autorizaciones_novena_tutoria"
        ordering = ("-fecha_autorizacion",)

    def __str__(self):
        return f"Novena tutoría autorizada · {self.proyecto}"

    def clean(self):
        if not str(self.motivo or "").strip():
            raise ValidationError({"motivo": "Explique el motivo de la novena tutoría."})


# ---------------------------------------------------------------------------
# Fase 7D — Examen complexivo (flujo independiente) y escala configurable
# ---------------------------------------------------------------------------


class EscalaCalificacion(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        db_column="programa_id",
        related_name="escalas_calificacion",
        blank=True,
        null=True,
        help_text="Nulo = escala global por defecto.",
    )
    modalidad = models.ForeignKey(
        ModalidadConfigurada,
        on_delete=models.PROTECT,
        db_column="modalidad_id",
        related_name="escalas_calificacion",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=100)
    nota_minima = models.DecimalField(max_digits=5, decimal_places=2)
    nota_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    nota_aprobacion = models.DecimalField(max_digits=5, decimal_places=2)
    esta_activa = models.BooleanField(db_default=True)

    class Meta:
        managed = False
        db_table = "escalas_calificacion"
        ordering = ("programa__nombre", "nombre")

    def __str__(self):
        return f"{self.nombre} ({self.nota_minima}-{self.nota_maxima})"

    def clean(self):
        if self.nota_minima is not None and self.nota_maxima is not None:
            if self.nota_maxima <= self.nota_minima:
                raise ValidationError({"nota_maxima": "Debe ser mayor a la nota mínima."})
            if self.nota_aprobacion is not None and not (
                self.nota_minima <= self.nota_aprobacion <= self.nota_maxima
            ):
                raise ValidationError(
                    {"nota_aprobacion": "Debe estar dentro del rango mínimo-máximo."}
                )


class ExamenComplexivo(ActualizacionMixin):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="examenes_complexivos",
    )
    escala = models.ForeignKey(
        EscalaCalificacion,
        on_delete=models.PROTECT,
        db_column="escala_id",
        blank=True,
        null=True,
        related_name="examenes",
    )
    convocatoria = models.CharField(max_length=150)
    fecha_hora = models.DateTimeField(blank=True, null=True)
    tribunal = models.TextField(
        blank=True,
        null=True,
        help_text="Nombres/roles de los miembros del tribunal o responsables.",
    )
    numero_intento = models.PositiveSmallIntegerField(db_default=1)
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    resultado = models.CharField(
        max_length=20,
        choices=ResultadoExamenComplexivo.choices,
        db_default=ResultadoExamenComplexivo.PENDIENTE,
    )
    observaciones = models.TextField(blank=True, null=True)
    acta_url = models.TextField(blank=True, null=True)
    fue_reprogramado = models.BooleanField(db_default=False)
    registrado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="registrado_por_id",
        blank=True,
        null=True,
        related_name="examenes_complexivos_registrados",
    )

    class Meta:
        managed = False
        db_table = "examenes_complexivos"
        ordering = ("proyecto_id", "-numero_intento")
        constraints = (
            models.UniqueConstraint(
                fields=("proyecto", "numero_intento"),
                name="uq_examen_complexivo_proyecto_intento",
            ),
        )

    def __str__(self):
        return f"{self.proyecto} · intento {self.numero_intento}"

    def clean(self):
        if self.escala_id and self.calificacion is not None:
            if not (self.escala.nota_minima <= self.calificacion <= self.escala.nota_maxima):
                raise ValidationError(
                    {"calificacion": "La calificación está fuera del rango de la escala configurada."}
                )
