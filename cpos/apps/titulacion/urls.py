from django.urls import path
from . import views

app_name = 'titulacion'

urlpatterns = [
    path('', views.dashboard_titulacion, name='dashboard'),
    path('tutores/', views.tutores_list, name='tutores_list'),
    path('tutores/crear/', views.tutor_create, name='tutor_create'),
    path('tutores/<int:pk>/', views.tutor_detail, name='tutor_detail'),
    path('tutores/<int:pk>/editar/', views.tutor_update, name='tutor_update'),
    path(
        'tutores/<int:pk>/estado/',
        views.tutor_toggle_estado,
        name='tutor_toggle_estado',
    ),
    path('expediente/', views.expediente, name='expediente'),
    path('proyecto/', views.proyecto, name='proyecto'),
    path('proyectos/crear/', views.proyecto_create, name='proyecto_create'),
    path('proyectos/<int:pk>/', views.proyecto_detail, name='proyecto_detail'),
    path('proyectos/<int:pk>/editar/', views.proyecto_update, name='proyecto_update'),
    path('proyectos/<int:pk>/enviar/', views.proyecto_enviar, name='proyecto_enviar'),
    path('proyectos/<int:pk>/revisar/', views.proyecto_revisar, name='proyecto_revisar'),
    path('proyectos/<int:pk>/resolucion/', views.proyecto_resolucion, name='proyecto_resolucion'),
    path('proyectos/<int:pk>/asignar-tutor/', views.asignacion_create, name='asignacion_create'),
    path('proyectos/<int:pk>/archivos/registrar/', views.archivo_create, name='archivo_create'),
    path('archivos/<int:pk>/descargar/', views.archivo_download, name='archivo_download'),
    path('archivos/<int:pk>/revisar/', views.archivo_revisar, name='archivo_revisar'),
    path('proyectos/<int:pk>/resolucion/descargar/', views.resolucion_download, name='resolucion_download'),
    path('proyectos/<int:pk>/tutorias/programar/', views.tutoria_create, name='tutoria_create'),
    path('tutorias/<int:pk>/registrar/', views.tutoria_registrar, name='tutoria_registrar'),
    path('tutorias/<int:pk>/reprogramar/', views.reprogramacion_create, name='reprogramacion_create'),
    path('reprogramaciones/<int:pk>/resolver/', views.reprogramacion_resolver, name='reprogramacion_resolver'),
    path('tutorias/<int:pk>/grabaciones/registrar/', views.grabacion_create, name='grabacion_create'),
    path('grabaciones/<int:pk>/descargar/', views.grabacion_download, name='grabacion_download'),
    path('grabaciones/<int:pk>/abrir/', views.grabacion_enlace, name='grabacion_enlace'),
    path('articulo/', views.articulo, name='articulo'),
    path('proyectos/<int:proyecto_pk>/articulo/editar/', views.articulo_edit, name='articulo_edit'),
    path('articulos/<int:pk>/revisar/', views.articulo_revisar, name='articulo_revisar'),
    path('proyectos/<int:proyecto_pk>/cambio-tema/', views.cambio_tema_create, name='cambio_tema_create'),
    path('cambios-tema/<int:pk>/resolver/', views.cambio_tema_resolver, name='cambio_tema_resolver'),
    path('aprobaciones/', views.aprobaciones, name='aprobaciones'),
    path('requerimientos/', views.requerimientos, name='requerimientos'),
]
