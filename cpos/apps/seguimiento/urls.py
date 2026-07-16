from django.urls import path

from . import views

app_name = "seguimiento"

urlpatterns = [
    # Dashboard principal
    path("", views.dashboard_seguimiento, name="dashboard"),

    # Tutorías
    path("tutorias/", views.lista_tutorias, name="tutorias"),
    path("tutorias/<int:tutoria_id>/", views.detalle_tutoria, name="detalle_tutoria"),
    path("tutorias/<int:tutoria_id>/asistencia/", views.registrar_asistencia, name="registrar_asistencia"),
    path("tutorias/<int:tutoria_id>/grabacion/", views.registrar_grabacion, name="registrar_grabacion"),
    path("grabaciones/<int:grabacion_id>/descargar/", views.grabacion_download, name="grabacion_download"),
    path("grabaciones/<int:grabacion_id>/abrir/", views.grabacion_enlace, name="grabacion_enlace"),
    path("tutorias/<int:tutoria_id>/evidencia/", views.subir_evidencia, name="subir_evidencia"),

    # Evidencias
    path("evidencias/", views.lista_evidencias, name="evidencias"),
    path("evidencias/<int:evidencia_id>/", views.detalle_evidencia, name="detalle_evidencia"),
    path("evidencias/<int:evidencia_id>/validar/", views.validar_evidencia, name="validar_evidencia"),
    path("evidencias/<int:evidencia_id>/corregir/", views.corregir_evidencia, name="corregir_evidencia"),
    path("evidencias/<int:evidencia_id>/historial/", views.historial_evidencia, name="historial_evidencia"),
    path("evidencias/<int:evidencia_id>/descargar/", views.descargar_evidencia, name="descargar_evidencia"),
    path("evidencias/versiones/<int:version_id>/descargar/", views.descargar_version, name="descargar_version"),

    # Artículo científico
    path("articulo/<int:proyecto_id>/", views.articulo_seguimiento, name="articulo"),
    path("articulo/<int:proyecto_id>/editar/<str:seccion>/", views.editar_seccion_articulo, name="editar_seccion_articulo"),
    path("articulo/<int:proyecto_id>/envio-revista/", views.registrar_envio_revista, name="registrar_envio_revista"),

    # Checklist de cierre
    path("checklist/<int:proyecto_id>/", views.checklist_cierre, name="checklist_cierre"),

    # Reportes
    path("reportes/", views.reportes_seguimiento, name="reportes"),

    # Notificaciones
    path("notificaciones/", views.notificaciones_seguimiento, name="notificaciones"),

    # Fase 7D - Entregas por etapa del producto final
    path("proyectos/<int:proyecto_id>/entregas-etapa/", views.lista_entregas_etapa, name="entregas_etapa"),
    path("proyectos/<int:proyecto_id>/entregas-etapa/<int:etapa_id>/subir/", views.subir_entrega_etapa, name="subir_entrega_etapa"),
    path("entregas-etapa/<int:entrega_id>/evaluar/", views.evaluar_entrega_etapa_view, name="evaluar_entrega_etapa"),
]
