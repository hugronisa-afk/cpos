from django.contrib import admin

from .models import (
    Aprobacion,
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    DocumentoProcesoAprobacion,
    DisponibilidadTutor,
    Grabacion,
    PasoAprobacion,
    ProcesoAprobacion,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    SolicitudCambioModalidad,
    SolicitudCambioTutor,
    Tutor,
    TutorPrograma,
    Tutoria,
)


@admin.register(ProyectoTitulacion)
class ProyectoTitulacionAdmin(admin.ModelAdmin):
    list_display = ("id", "maestrante", "modalidad", "estado", "esta_activo")
    list_filter = ("modalidad", "estado", "esta_activo")
    search_fields = ("tema", "maestrante__usuario__nombres", "maestrante__usuario__apellidos")


@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "especialidad", "estado")
    list_filter = ("estado",)
    search_fields = ("usuario__nombres", "usuario__apellidos", "especialidad")


@admin.register(Tutoria)
class TutoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "proyecto", "numero_tutoria", "fecha", "estado")
    list_filter = ("estado", "fecha")


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ("id", "proyecto", "estado", "porcentaje_avance", "esta_activo")
    list_filter = ("estado", "esta_activo")


admin.site.register(AsignacionTutor)
admin.site.register(AsistenciaTutoria)
admin.site.register(ReprogramacionTutoria)
admin.site.register(ArchivoProyecto)
admin.site.register(Grabacion)
admin.site.register(SolicitudCambioTema)
admin.site.register(SolicitudCambioModalidad)
admin.site.register(Aprobacion)
admin.site.register(ProcesoAprobacion)
admin.site.register(PasoAprobacion)
admin.site.register(DocumentoProcesoAprobacion)
admin.site.register(TutorPrograma)
admin.site.register(DisponibilidadTutor)
admin.site.register(SolicitudCambioTutor)
