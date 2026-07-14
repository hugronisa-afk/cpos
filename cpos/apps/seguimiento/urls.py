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
    path("tutorias/<int:tutoria_id>/evidencia/", views.subir_evidencia, name="subir_evidencia"),

    # Evidencias
    path("evidencias/", views.lista_evidencias, name="evidencias"),
    path("evidencias/<int:evidencia_id>/", views.detalle_evidencia, name="detalle_evidencia"),
    path("evidencias/<int:evidencia_id>/validar/", views.validar_evidencia, name="validar_evidencia"),
    path("evidencias/<int:evidencia_id>/corregir/", views.corregir_evidencia, name="corregir_evidencia"),
    path("evidencias/<int:evidencia_id>/historial/", views.historial_evidencia, name="historial_evidencia"),

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
]