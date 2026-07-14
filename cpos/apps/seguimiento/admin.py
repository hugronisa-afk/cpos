from django.contrib import admin

from .models import (
    Tutoria,
    AsistenciaTutoria,
    ReprogramacionTutoria,
    Grabacion,
    Evidencia,
    EvidenciaVersion,
    ValidacionEvidencia,
    Articulo,
    Notificacion,
)


@admin.register(Tutoria)
class TutoriaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero",
        "proyecto",
        "tutor",
        "fecha",
        "hora_inicio",
        "hora_fin",
        "estado",
    )
    list_filter = (
        "estado",
        "fecha",
    )
    search_fields = (
        "tema",
        "descripcion",
        "proyecto__titulo",
        "tutor__usuario__nombres",
        "tutor__usuario__apellidos",
        "tutor__usuario__email",
    )
    ordering = (
        "fecha",
        "hora_inicio",
        "numero",
    )


@admin.register(AsistenciaTutoria)
class AsistenciaTutoriaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tutoria",
        "usuario",
        "tipo_participante",
        "asistio",
        "fecha_registro",
    )
    list_filter = (
        "tipo_participante",
        "asistio",
        "fecha_registro",
    )
    search_fields = (
        "usuario__nombres",
        "usuario__apellidos",
        "usuario__email",
        "tutoria__tema",
    )


@admin.register(ReprogramacionTutoria)
class ReprogramacionTutoriaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tutoria",
        "fecha_anterior",
        "fecha_nueva",
        "estado",
        "solicitado_por",
        "aprobado_por",
    )
    list_filter = (
        "estado",
        "fecha_anterior",
        "fecha_nueva",
    )
    search_fields = (
        "motivo",
        "tutoria__tema",
        "solicitado_por__email",
        "aprobado_por__email",
    )


@admin.register(Grabacion)
class GrabacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "proyecto",
        "tutoria",
        "enlace",
        "registrado_por",
        "fecha_registro",
    )
    list_filter = (
        "fecha_registro",
    )
    search_fields = (
        "proyecto__titulo",
        "tutoria__tema",
        "enlace",
        "registrado_por__email",
    )


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titulo",
        "tipo_avance",
        "estado",
        "proyecto",
        "tutoria",
        "cargado_por",
        "fecha_carga",
    )
    list_filter = (
        "tipo_avance",
        "estado",
        "fecha_carga",
    )
    search_fields = (
        "titulo",
        "descripcion",
        "proyecto__titulo",
        "tutoria__tema",
        "cargado_por__email",
    )
    ordering = (
        "-fecha_carga",
        "-id",
    )


@admin.register(EvidenciaVersion)
class EvidenciaVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "evidencia",
        "numero_version",
        "creado_por",
        "creado_en",
    )
    list_filter = (
        "numero_version",
        "creado_en",
    )
    search_fields = (
        "evidencia__titulo",
        "descripcion_cambios",
        "creado_por__email",
    )
    ordering = (
        "-creado_en",
        "-numero_version",
    )


@admin.register(ValidacionEvidencia)
class ValidacionEvidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "evidencia",
        "tutor",
        "estado",
        "validado_por",
        "fecha_validacion",
    )
    list_filter = (
        "estado",
        "fecha_validacion",
    )
    search_fields = (
        "evidencia__titulo",
        "observaciones",
        "validado_por__email",
        "tutor__usuario__email",
    )
    ordering = (
        "-fecha_validacion",
        "-id",
    )


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "proyecto",
        "estado",
        "revista_nombre",
        "fecha_envio_revista",
        "estado_respuesta_revista",
    )
    list_filter = (
        "estado",
        "fecha_envio_revista",
        "estado_respuesta_revista",
    )
    search_fields = (
        "titulo",
        "proyecto__titulo",
        "revista_nombre",
    )


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "titulo",
        "tipo",
        "leida",
        "creado_en",
    )
    list_filter = (
        "tipo",
        "leida",
        "creado_en",
    )
    search_fields = (
        "titulo",
        "mensaje",
        "usuario__email",
        "usuario__nombres",
        "usuario__apellidos",
    )
    ordering = (
        "-creado_en",
        "-id",
    )