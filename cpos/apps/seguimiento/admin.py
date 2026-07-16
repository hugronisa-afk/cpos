from django.contrib import admin

from .models import Evidencia, EvidenciaVersion, Notificacion, ValidacionEvidencia


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titulo",
        "tipo_avance",
        "estado",
        "proyecto",
        "tutoria",
        "subido_por",
        "version_actual",
        "fecha_creacion",
    )
    list_filter = ("tipo_avance", "estado", "fecha_creacion")
    search_fields = (
        "titulo",
        "descripcion",
        "proyecto__tema",
        "subido_por__correo",
    )
    ordering = ("-fecha_creacion", "-id")


@admin.register(EvidenciaVersion)
class EvidenciaVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "evidencia",
        "numero_version",
        "subido_por",
        "fecha_creacion",
    )
    list_filter = ("numero_version", "fecha_creacion")
    search_fields = (
        "evidencia__titulo",
        "comentario",
        "subido_por__correo",
    )
    ordering = ("-fecha_creacion", "-numero_version")


@admin.register(ValidacionEvidencia)
class ValidacionEvidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "evidencia",
        "estado_resultado",
        "validado_por",
        "fecha_creacion",
    )
    list_filter = ("estado_resultado", "fecha_creacion")
    search_fields = (
        "evidencia__titulo",
        "observaciones",
        "validado_por__correo",
    )
    ordering = ("-fecha_creacion", "-id")


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "titulo",
        "tipo",
        "estado",
        "fecha_envio",
        "fecha_lectura",
    )
    list_filter = ("tipo", "estado", "fecha_creacion")
    search_fields = (
        "titulo",
        "mensaje",
        "usuario__correo",
        "usuario__nombres",
        "usuario__apellidos",
    )
    ordering = ("-fecha_creacion", "-id")
