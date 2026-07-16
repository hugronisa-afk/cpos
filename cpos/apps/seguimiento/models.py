"""Modelos propios del seguimiento académico.

Accounts y Titulación son los dueños de usuarios, proyectos, tutores, tutorías,
asistencias, grabaciones, artículos y aprobaciones. Seguimiento reutiliza esos
modelos y solo declara las tablas cuyo contrato le pertenece: evidencias,
versiones, validaciones y notificaciones.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Now

from apps.accounts.models import UsuarioCPOS
from apps.titulacion.models import ProyectoTitulacion, Tutoria


TIPO_EVIDENCIA_CHOICES = (
    ("busqueda_bibliografica", "Búsqueda bibliográfica"),
    ("titulo", "Título"),
    ("introduccion", "Introducción"),
    ("planteamiento_problema", "Planteamiento del problema"),
    ("marco_teorico", "Marco teórico"),
    ("metodologia", "Metodología"),
    ("analisis", "Análisis"),
    ("resultados", "Resultados"),
    ("conclusiones", "Conclusiones"),
    ("referencias", "Referencias"),
    ("documento_final", "Documento final"),
    ("anexos", "Anexos"),
    ("plan_estudio", "Plan de estudio"),
    ("banco_preguntas", "Banco de preguntas"),
    ("simulacion", "Simulación"),
    ("acta_resultado", "Acta o resultado"),
    ("otro", "Otro"),
)

ESTADO_EVIDENCIA_CHOICES = (
    ("pendiente", "Pendiente"),
    ("en_revision", "En revisión"),
    ("validada", "Validada"),
    ("observada", "Observada"),
    ("rechazada", "Rechazada"),
)

ESTADO_VALIDACION_CHOICES = (
    ("validada", "Validada"),
    ("observada", "Observada"),
    ("rechazada", "Rechazada"),
)

SECCION_ARTICULO_CHOICES = (
    ("titulo", "Título"),
    ("introduccion", "Introducción"),
    ("metodologia", "Metodología"),
    ("resultados", "Resultados"),
    ("conclusiones", "Conclusiones"),
    ("referencias", "Referencias"),
)


class Evidencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    proyecto = models.ForeignKey(
        ProyectoTitulacion,
        on_delete=models.PROTECT,
        db_column="proyecto_id",
        related_name="evidencias_seguimiento",
    )
    tutoria = models.ForeignKey(
        Tutoria,
        on_delete=models.PROTECT,
        db_column="tutoria_id",
        related_name="evidencias_seguimiento",
    )
    subido_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="subido_por_id",
        blank=True,
        null=True,
        related_name="evidencias_subidas",
    )
    tipo_avance = models.CharField(max_length=50, choices=TIPO_EVIDENCIA_CHOICES)
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    archivo_url = models.TextField()
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_EVIDENCIA_CHOICES,
        db_default="pendiente",
    )
    version_actual = models.PositiveIntegerField(db_default=1)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "evidencias"
        ordering = ("-fecha_creacion", "-id")
        verbose_name = "evidencia"
        verbose_name_plural = "evidencias"

    def __str__(self):
        return self.titulo

    def clean(self):
        if self.tutoria_id and self.proyecto_id:
            proyecto_tutoria = getattr(self.tutoria, "proyecto_id", None)
            if proyecto_tutoria != self.proyecto_id:
                raise ValidationError(
                    "La evidencia no puede asociarse a una tutoría de otro proyecto."
                )
        if not str(self.archivo_url or "").strip():
            raise ValidationError({"archivo_url": "La evidencia debe tener un archivo."})


class EvidenciaVersion(models.Model):
    id = models.BigAutoField(primary_key=True)
    evidencia = models.ForeignKey(
        Evidencia,
        on_delete=models.PROTECT,
        db_column="evidencia_id",
        related_name="versiones",
    )
    numero_version = models.PositiveIntegerField()
    archivo_url = models.TextField()
    comentario = models.TextField(blank=True, null=True)
    subido_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="subido_por_id",
        blank=True,
        null=True,
        related_name="versiones_evidencia_subidas",
    )
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "evidencia_versiones"
        ordering = ("-numero_version", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("evidencia", "numero_version"),
                name="uq_evidencia_version",
            ),
        )
        verbose_name = "versión de evidencia"
        verbose_name_plural = "versiones de evidencias"

    def __str__(self):
        return f"Evidencia {self.evidencia_id} - versión {self.numero_version}"


class ValidacionEvidencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    evidencia = models.ForeignKey(
        Evidencia,
        on_delete=models.PROTECT,
        db_column="evidencia_id",
        related_name="validaciones",
    )
    validado_por = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.SET_NULL,
        db_column="validado_por_id",
        blank=True,
        null=True,
        related_name="validaciones_evidencia_realizadas",
    )
    estado_resultado = models.CharField(
        max_length=30,
        choices=ESTADO_VALIDACION_CHOICES,
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        managed = False
        db_table = "validaciones_evidencia"
        ordering = ("-fecha_creacion", "-id")
        verbose_name = "validación de evidencia"
        verbose_name_plural = "validaciones de evidencias"

    def __str__(self):
        return f"Evidencia {self.evidencia_id} - {self.estado_resultado}"


class Notificacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        UsuarioCPOS,
        on_delete=models.PROTECT,
        db_column="usuario_id",
        related_name="notificaciones_seguimiento",
    )
    tipo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    estado = models.CharField(max_length=30, db_default="pendiente")
    fecha_envio = models.DateTimeField(blank=True, null=True)
    fecha_lectura = models.DateTimeField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(db_default=Now(), editable=False)
    fecha_actualizacion = models.DateTimeField(db_default=Now())

    class Meta:
        managed = False
        db_table = "notificaciones"
        ordering = ("-fecha_creacion", "-id")
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return self.titulo


# Compatibilidad de importación. Estos modelos tienen un único dueño y no se
# vuelven a declarar en Seguimiento.
from apps.accounts.models import Bitacora, Maestrante, Programa, Rol  # noqa: E402,F401
from apps.titulacion.models import (  # noqa: E402,F401
    Aprobacion,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    Grabacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    Tutor,
)

Usuario = UsuarioCPOS
