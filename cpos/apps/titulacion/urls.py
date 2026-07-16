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
    path('tutores/<int:pk>/disponibilidad/crear/', views.tutor_disponibilidad_create, name='tutor_disponibilidad_create'),
    path('tutores/disponibilidades/<int:pk>/estado/', views.tutor_disponibilidad_toggle, name='tutor_disponibilidad_toggle'),
    path('calendario/', views.calendario_tutorias, name='calendario_tutorias'),
    path('expediente/', views.expediente, name='expediente'),
    path('proyecto/', views.proyecto, name='proyecto'),
    path('proyectos/crear/', views.proyecto_create, name='proyecto_create'),
    path('proyectos/<int:pk>/', views.proyecto_detail, name='proyecto_detail'),
    path('proyectos/<int:pk>/editar/', views.proyecto_update, name='proyecto_update'),
    path('proyectos/<int:pk>/enviar/', views.proyecto_enviar, name='proyecto_enviar'),
    path('proyectos/<int:pk>/revisar/', views.proyecto_revisar, name='proyecto_revisar'),
    path('proyectos/<int:pk>/resolucion/', views.proyecto_resolucion, name='proyecto_resolucion'),
    path('proyectos/<int:pk>/asignar-tutor/', views.asignacion_create, name='asignacion_create'),
    path('proyectos/<int:proyecto_pk>/cambio-tutor/', views.cambio_tutor_create, name='cambio_tutor_create'),
    path('cambios-tutor/<int:pk>/resolver/', views.cambio_tutor_resolver, name='cambio_tutor_resolver'),
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
    path('proyectos/<int:proyecto_pk>/cambio-modalidad/', views.cambio_modalidad_create, name='cambio_modalidad_create'),
    path('cambios-modalidad/<int:pk>/resolver/', views.cambio_modalidad_resolver, name='cambio_modalidad_resolver'),
    path('aprobaciones/procesos/<int:pk>/', views.proceso_aprobacion_detail, name='proceso_aprobacion_detail'),
    path('aprobaciones/pasos/<int:pk>/resolver/', views.paso_aprobacion_resolver, name='paso_aprobacion_resolver'),
    path('modalidades/configuracion/', views.modalidades_configuracion, name='modalidades_configuracion'),
    path('aprobaciones/', views.aprobaciones, name='aprobaciones'),
    path('requerimientos/', views.requerimientos, name='requerimientos'),

    # Fase 7A - Onboarding obligatorio
    path('onboarding/', views.onboarding_gate, name='onboarding_gate'),
    path('onboarding/iniciar/', views.onboarding_iniciar, name='onboarding_iniciar'),

    # Fase 7B - Modalidades configuradas y etapas
    path('modalidades/configuradas/', views.modalidades_configuradas_list, name='modalidades_configuradas_list'),
    path('modalidades/configuradas/crear/', views.modalidad_configurada_create, name='modalidad_configurada_create'),
    path('modalidades/configuradas/<int:pk>/editar/', views.modalidad_configurada_update, name='modalidad_configurada_update'),
    path('modalidades/configuradas/<int:pk>/estado/', views.modalidad_configurada_toggle, name='modalidad_configurada_toggle'),
    path('modalidades/configuradas/<int:modalidad_pk>/etapas/crear/', views.etapa_producto_create, name='etapa_producto_create'),
    path('etapas/<int:pk>/editar/', views.etapa_producto_update, name='etapa_producto_update'),
    path('etapas/<int:pk>/estado/', views.etapa_producto_toggle, name='etapa_producto_toggle'),

    # Fase 7C - Novena tutoria excepcional
    path('proyectos/<int:proyecto_pk>/novena-tutoria/autorizar/', views.novena_tutoria_autorizar, name='novena_tutoria_autorizar'),

    # Fase 7D - Examen complexivo y escalas de calificacion
    path('examenes-complexivos/', views.examenes_complexivos_list, name='examenes_complexivos_list'),
    path('proyectos/<int:proyecto_pk>/examen-complexivo/crear/', views.examen_complexivo_create, name='examen_complexivo_create'),
    path('examenes-complexivos/<int:pk>/editar/', views.examen_complexivo_update, name='examen_complexivo_update'),
    path('escalas-calificacion/crear/', views.escala_calificacion_create, name='escala_calificacion_create'),
    path('escalas-calificacion/<int:pk>/editar/', views.escala_calificacion_update, name='escala_calificacion_update'),
]
