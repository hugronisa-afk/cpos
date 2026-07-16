from datetime import date
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from urllib.parse import urlparse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import permiso_required, usuario_activo_required
from apps.accounts.models import Programa
from apps.accounts.services import usuario_tiene_permiso

from .forms import (
    ArchivoProyectoForm,
    ArticuloForm,
    AsignacionTutorForm,
    AutorizacionNovenaTutoriaForm,
    ConfiguracionModalidadProgramaForm,
    DisponibilidadTutorForm,
    EntregaEtapaForm,
    EscalaCalificacionForm,
    EtapaProductoForm,
    EvaluarEntregaEtapaForm,
    ExamenComplexivoForm,
    GrabacionForm,
    ModalidadConfiguradaForm,
    ProyectoForm,
    RegistroTutoriaForm,
    ReprogramacionTutoriaForm,
    ResolucionProyectoForm,
    RevisionArchivoForm,
    RevisionArticuloForm,
    RevisionPasoAprobacionForm,
    ResolucionCambioTutorForm,
    SeleccionModalidadOnboardingForm,
    SolicitudCambioTutorForm,
    SolicitudCambioTemaForm,
    SolicitudCambioModalidadForm,
    TutorForm,
    TutoriaForm,
)
from .models import (
    Aprobacion,
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    AutorizacionNovenaTutoria,
    ConfiguracionModalidadPrograma,
    DisponibilidadTutor,
    DocumentoProcesoAprobacion,
    EntregaEtapa,
    EscalaCalificacion,
    EstadoAsignacion,
    EstadoEtapaProducto,
    EstadoOnboarding,
    EstadoProyecto,
    EstadoReprogramacion,
    EstadoSolicitudCambioTutor,
    EstadoTutoria,
    EstadoTutor,
    EtapaProducto,
    ExamenComplexivo,
    Grabacion,
    ModalidadConfigurada,
    ModalidadProyecto,
    OnboardingMaestrante,
    PasoAprobacion,
    ProcesoAprobacion,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTutor,
    SolicitudCambioTema,
    SolicitudCambioModalidad,
    Tutor,
    TutorPrograma,
    Tutoria,
    TipoProcesoAprobacion,
    TipoDocumentoAprobacion,
)
from .aprobaciones import (
    iniciar_proceso_cambio,
    iniciar_revision_proyecto,
    obtener_proceso_visible,
    proceso_activo_proyecto,
    procesos_visibles,
    puede_resolver_paso,
    resolver_paso,
)
from .modalidades import modalidades_disponibles, obtener_regla_modalidad
from .services import (
    asignar_tutor,
    autorizar_novena_tutoria,
    completar_onboarding,
    crear_entrega_etapa,
    etapa_esta_bloqueada,
    etapas_de_modalidad,
    evaluar_entrega_etapa,
    iniciar_onboarding,
    maestrante_es_elegible_onboarding,
    modalidades_configuradas_activas,
    obtener_onboarding_maestrante,
    programar_tutoria,
    obtener_proyecto_visible,
    puede_autorizar_novena_tutoria,
    puede_crear_proyecto,
    puede_editar_articulo,
    puede_editar_proyecto,
    puede_evaluar_entrega_etapa,
    puede_gestionar_programacion,
    puede_registrar_sesion,
    puede_revisar_articulo,
    puede_revisar_archivo,
    puede_solicitar_cambio_tutor,
    puede_revisar_cambio_tema,
    puede_revisar_cambio_modalidad,
    puede_solicitar_cambio_tema,
    puede_solicitar_cambio_modalidad,
    puede_subir_entrega_etapa,
    proyectos_visibles,
    registrar_evento,
    registrar_solicitud_aprobacion,
    resolver_revision_archivo,
    resolver_reprogramacion,
    resolver_cambio_tutor,
    resumen_evidencias,
    rol_usuario,
    tiene_autorizacion_novena_tutoria,
    solicitar_cambio_tutor,
    solicitar_reprogramacion,
)
from .storage import (
    ErrorAlmacenamiento,
    MAX_DOCUMENTO,
    MAX_GRABACION,
    eliminar_archivo,
    guardar_archivo,
    respuesta_descarga,
)


def _exigir_rol(request, *roles):
    if rol_usuario(request.user) not in roles:
        raise PermissionDenied("Su rol no puede realizar esta acción.")


def _mensaje_validacion(request, error):
    if hasattr(error, "messages"):
        for mensaje in error.messages:
            messages.error(request, mensaje)
    else:
        messages.error(request, str(error))


def _consulta_tutores():
    return Tutor.objects.select_related("usuario", "usuario__rol").prefetch_related(
        "vinculos_programa__programa", "disponibilidades"
    ).annotate(
        carga_activa=Count(
            "asignaciones",
            filter=Q(asignaciones__estado=EstadoAsignacion.ACTIVO),
            distinct=True,
        )
    )


def _tutores_visibles(usuario):
    consulta = _consulta_tutores()
    rol = rol_usuario(usuario)
    if rol == "coordinador":
        return consulta.filter(
            vinculos_programa__programa__coordinador_id=usuario.pk,
            vinculos_programa__esta_activo=True,
        ).distinct()
    if rol == "supervisor":
        return consulta
    if rol == "tutor":
        return consulta.filter(usuario_id=usuario.pk)
    return consulta.none()


@usuario_activo_required
def dashboard_titulacion(request):
    proyectos = proyectos_visibles(request.user)
    estadisticas = proyectos.aggregate(
        total=Count("id", distinct=True),
        aprobados=Count("id", filter=Q(estado=EstadoProyecto.APROBADO), distinct=True),
        en_revision=Count("id", filter=Q(estado=EstadoProyecto.EN_REVISION), distinct=True),
        observados=Count("id", filter=Q(estado=EstadoProyecto.OBSERVADO), distinct=True),
        avance_articulo=Avg("articulos__porcentaje_avance"),
    )
    proyecto_actual = proyectos.first()
    return render(
        request,
        "titulacion/dashboard.html",
        {
            "estadisticas": estadisticas,
            "proyecto_actual": proyecto_actual,
            "proximas_tutorias": Tutoria.objects.filter(proyecto__in=proyectos).select_related("proyecto", "tutor__usuario").order_by("fecha", "hora_inicio")[:5],
            "evidencias": resumen_evidencias(proyecto_actual) if proyecto_actual else {"integrado": False},
            "rol_actual": rol_usuario(request.user),
            "page_title": "Panel de titulación",
            "page_subtitle": "Información real limitada al alcance de su rol",
            "active_page": "titulacion_dashboard",
        },
    )


@usuario_activo_required
def expediente(request):
    proyectos = proyectos_visibles(request.user)
    proyecto_id = request.GET.get("proyecto", "").strip()
    proyecto_actual = get_object_or_404(proyectos, pk=proyecto_id) if proyecto_id.isdigit() else proyectos.first()
    asignacion = None
    if proyecto_actual:
        asignacion = proyecto_actual.asignaciones_tutor.select_related("tutor__usuario").filter(estado=EstadoAsignacion.ACTIVO).first()
    return render(
        request,
        "titulacion/expediente.html",
        {
            "proyectos": proyectos,
            "proyecto": proyecto_actual,
            "asignacion": asignacion,
            "evidencias": resumen_evidencias(proyecto_actual) if proyecto_actual else {"integrado": False},
            "rol_actual": rol_usuario(request.user),
            "page_title": "Expediente",
            "page_subtitle": "Expediente académico según su alcance",
            "active_page": "expediente",
        },
    )


@usuario_activo_required
def proyecto(request):
    consulta = proyectos_visibles(request.user)
    busqueda = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    if busqueda:
        consulta = consulta.filter(Q(tema__icontains=busqueda) | Q(maestrante__usuario__nombres__icontains=busqueda) | Q(maestrante__usuario__apellidos__icontains=busqueda))
    if estado in {valor for valor, _ in EstadoProyecto.choices}:
        consulta = consulta.filter(estado=estado)
    else:
        estado = ""
    return render(
        request,
        "titulacion/proyecto.html",
        {
            "pagina": Paginator(consulta, 20).get_page(request.GET.get("page")),
            "busqueda": busqueda,
            "estado_seleccionado": estado,
            "estados": EstadoProyecto.choices,
            "puede_crear": puede_crear_proyecto(request.user),
            "rol_actual": rol_usuario(request.user),
            "page_title": "Proyectos de titulación",
            "page_subtitle": "Proyectos reales visibles para su rol",
            "active_page": "proyecto",
        },
    )


@usuario_activo_required
def proyecto_detail(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    regla_modalidad = obtener_regla_modalidad(
        proyecto_obj.maestrante.programa,
        proyecto_obj.modalidad,
    )
    asignacion = proyecto_obj.asignaciones_tutor.select_related("tutor__usuario").filter(estado=EstadoAsignacion.ACTIVO).first()
    asignaciones_tutor = proyecto_obj.asignaciones_tutor.select_related(
        "tutor__usuario", "asignado_por"
    ).all()
    cambios_tutor = proyecto_obj.solicitudes_cambio_tutor.select_related(
        "asignacion_actual__tutor__usuario",
        "tutor_propuesto__usuario",
        "solicitado_por",
        "resuelto_por",
    ).all()
    procesos = list(
        proyecto_obj.procesos_aprobacion.select_related("creado_por")
        .prefetch_related("pasos__resuelto_por", "documentos__archivo")
        .all()
    )
    proceso_actual = next(
        (item for item in procesos if item.estado == "en_curso"),
        None,
    )
    paso_actual = (
        proceso_actual.pasos.filter(estado="activo").first()
        if proceso_actual
        else None
    )
    archivos = list(proyecto_obj.archivos.select_related("subido_por").all())
    decisiones_archivos = Aprobacion.objects.filter(
        proyecto=proyecto_obj,
        tipo_aprobacion="archivo_proyecto",
        referencia_tabla="archivos_proyecto",
        referencia_id__in=[archivo.pk for archivo in archivos],
    ).order_by("referencia_id", "-fecha_creacion")
    decisiones_por_archivo = {}
    for decision in decisiones_archivos:
        decisiones_por_archivo.setdefault(decision.referencia_id, decision)
    for archivo in archivos:
        archivo.aprobacion_actual = decisiones_por_archivo.get(archivo.pk)
    return render(
        request,
        "titulacion/proyecto_detail.html",
        {
            "proyecto": proyecto_obj,
            "asignacion": asignacion,
            "asignaciones_tutor": asignaciones_tutor,
            "cambios_tutor": cambios_tutor,
            "tutorias": proyecto_obj.tutorias.select_related("tutor__usuario").prefetch_related("grabaciones", "reprogramaciones").all(),
            "archivos": archivos,
            "articulos": proyecto_obj.articulos.filter(esta_activo=True),
            "cambios_tema": proyecto_obj.solicitudes_cambio_tema.select_related("solicitado_por").all(),
            "cambios_modalidad": proyecto_obj.solicitudes_cambio_modalidad.select_related(
                "solicitado_por", "resuelto_por"
            ).all(),
            "regla_modalidad": regla_modalidad,
            "procesos_aprobacion": procesos,
            "proceso_actual": proceso_actual,
            "paso_actual": paso_actual,
            "puede_editar": puede_editar_proyecto(request.user, proyecto_obj),
            "puede_revisar": bool(
                paso_actual and puede_resolver_paso(request.user, paso_actual)
            ),
            "puede_aprobar": False,
            "puede_asignar": not asignacion and proyecto_obj.estado == EstadoProyecto.APROBADO and rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "ASIGNACION_TUTOR_CREAR"),
            "puede_solicitar_cambio_tutor": puede_solicitar_cambio_tutor(
                request.user, proyecto_obj
            ),
            "puede_resolver_cambio_tutor": rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "CAMBIO_TUTOR_GESTIONAR"),
            "puede_registrar_resolucion": proyecto_obj.estado == EstadoProyecto.APROBADO and not proyecto_obj.documento_resolucion_url and rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "PROYECTO_RESOLUCION_REGISTRAR"),
            "puede_programar": puede_gestionar_programacion(request.user, proyecto_obj),
            "total_tutorias": proyecto_obj.tutorias.count(),
            "tiene_novena_autorizada": tiene_autorizacion_novena_tutoria(proyecto_obj),
            "limite_tutorias": 9 if tiene_autorizacion_novena_tutoria(proyecto_obj) else 8,
            "puede_autorizar_novena": (
                proyecto_obj.tutorias.count() >= 8
                and not tiene_autorizacion_novena_tutoria(proyecto_obj)
                and puede_autorizar_novena_tutoria(request.user)
            ),
            "tutorias_vencidas": proyecto_obj.tutorias.filter(
                fecha__lt=timezone.localdate(),
                estado__in=[EstadoTutoria.PROGRAMADA, EstadoTutoria.REPROGRAMADA],
            ).count(),
            "puede_subir_archivo": puede_editar_proyecto(request.user, proyecto_obj) and usuario_tiene_permiso(request.user, "ARCHIVO_SUBIR"),
            "puede_cambio_tema": not proceso_actual and puede_solicitar_cambio_tema(request.user, proyecto_obj),
            "puede_revisar_cambio_tema": puede_revisar_cambio_tema(request.user, proyecto_obj),
            "puede_cambio_modalidad": not proceso_actual and puede_solicitar_cambio_modalidad(request.user, proyecto_obj),
            "puede_revisar_cambio_modalidad": puede_revisar_cambio_modalidad(
                request.user, proyecto_obj
            ),
            "evidencias": resumen_evidencias(proyecto_obj),
            "rol_actual": rol_usuario(request.user),
            "page_title": "Detalle del proyecto",
            "page_subtitle": proyecto_obj.tema,
            "active_page": "proyecto",
        },
    )


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def proyecto_create(request):
    if not puede_crear_proyecto(request.user):
        raise PermissionDenied("No puede crear otro proyecto de titulación.")
    formulario = ProyectoForm(
        request.POST or None,
        programa=request.user.perfil_maestrante.programa,
    )
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            proyecto_obj = formulario.save(commit=False)
            proyecto_obj.maestrante = request.user.perfil_maestrante
            proyecto_obj.creado_por = request.user
            proyecto_obj.actualizado_por = request.user
            proyecto_obj.save()
            proyecto_obj.maestrante.estado_titulacion = "proyecto_borrador"
            proyecto_obj.maestrante.save(update_fields=("estado_titulacion", "fecha_actualizacion"))
            registrar_evento(request, accion="crear_proyecto", tabla="proyectos_titulacion", registro_id=proyecto_obj.pk, descripcion="El maestrante creó su proyecto de titulación.")
        messages.success(request, "Proyecto creado. Puede editarlo antes de enviarlo a revisión.")
        return redirect("titulacion:proyecto_detail", pk=proyecto_obj.pk)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Crear proyecto", "page_title": "Crear proyecto", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def proyecto_update(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not puede_editar_proyecto(request.user, proyecto_obj):
        raise PermissionDenied("El proyecto no es editable en su estado actual.")
    formulario = ProyectoForm(
        request.POST or None,
        instance=proyecto_obj,
        programa=proyecto_obj.maestrante.programa,
    )
    if request.method == "POST" and formulario.is_valid():
        proyecto_obj = formulario.save(commit=False)
        proyecto_obj.actualizado_por = request.user
        proyecto_obj.save()
        registrar_evento(request, accion="editar_proyecto", tabla="proyectos_titulacion", registro_id=proyecto_obj.pk, descripcion="Se editó el borrador del proyecto.")
        messages.success(request, "Proyecto actualizado.")
        return redirect("titulacion:proyecto_detail", pk=pk)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Editar proyecto", "page_title": "Editar proyecto", "active_page": "proyecto"})


@usuario_activo_required
@require_POST
def proyecto_enviar(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    try:
        proceso = iniciar_revision_proyecto(proyecto_obj, request.user, request)
        messages.success(
            request,
            f"Proyecto enviado a revisión formal, versión {proceso.numero_version}.",
        )
    except (PermissionDenied, ValidationError) as error:
        _mensaje_validacion(request, error)
    return redirect("titulacion:proyecto_detail", pk=pk)


@usuario_activo_required
@require_http_methods(["GET"])
def proyecto_revisar(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    proceso = proceso_activo_proyecto(proyecto_obj)
    if not proceso:
        raise PermissionDenied("El proyecto no tiene una revisión formal activa.")
    return redirect("titulacion:proceso_aprobacion_detail", pk=proceso.pk)


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def proyecto_resolucion(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not (
        rol_usuario(request.user) == "coordinador"
        and proyecto_obj.estado == EstadoProyecto.APROBADO
        and not proyecto_obj.documento_resolucion_url
        and usuario_tiene_permiso(request.user, "PROYECTO_RESOLUCION_REGISTRAR")
    ):
        raise PermissionDenied("Solo coordinación puede registrar la resolución.")
    formulario = ResolucionProyectoForm(
        request.POST or None,
        request.FILES or None,
        instance=proyecto_obj,
    )
    if request.method == "POST" and formulario.is_valid():
        referencia_nueva = None
        datos = None
        try:
            documento = formulario.cleaned_data.get("documento_resolucion")
            if documento:
                datos = guardar_archivo(
                    documento,
                    categoria="resoluciones",
                    proyecto_id=proyecto_obj.pk,
                    extensiones={"pdf"},
                    limite_bytes=MAX_DOCUMENTO,
                )
                referencia_nueva = datos["referencia"]
            with transaction.atomic():
                proyecto_obj = formulario.save(commit=False)
                if referencia_nueva:
                    proyecto_obj.documento_resolucion_url = referencia_nueva
                proyecto_obj.actualizado_por = request.user
                proyecto_obj.save()
                archivo_resolucion = ArchivoProyecto.objects.create(
                    proyecto=proyecto_obj,
                    tipo_archivo="resolucion",
                    nombre_original=documento.name,
                    ruta_archivo=datos["referencia"],
                    extension=datos["extension"],
                    tamano_bytes=datos["tamano_bytes"],
                    subido_por=request.user,
                )
                proceso_aprobado = ProcesoAprobacion.objects.filter(
                    proyecto=proyecto_obj,
                    tipo=TipoProcesoAprobacion.PROYECTO,
                    estado="aprobado",
                ).order_by("-fecha_finalizacion", "-id").first()
                if proceso_aprobado:
                    DocumentoProcesoAprobacion.objects.update_or_create(
                        proceso=proceso_aprobado,
                        tipo_documento=TipoDocumentoAprobacion.RESOLUCION,
                        defaults={"archivo": archivo_resolucion},
                    )
                registrar_evento(request, accion="registrar_resolucion", tabla="proyectos_titulacion", registro_id=pk, descripcion="Se registró la resolución del proyecto.")
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
            return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Registrar resolución", "page_title": "Resolución", "active_page": "proyecto"})
        except Exception:
            if referencia_nueva:
                eliminar_archivo(referencia_nueva)
            raise
        messages.success(request, "Resolución registrada.")
        return redirect("titulacion:proyecto_detail", pk=pk)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Registrar resolución", "page_title": "Resolución", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def asignacion_create(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    _exigir_rol(request, "coordinador")
    if proyecto_obj.estado != EstadoProyecto.APROBADO:
        raise PermissionDenied("El proyecto debe estar aprobado antes de asignar tutor.")
    formulario = AsignacionTutorForm(request.POST or None, proyecto=proyecto_obj)
    if request.method == "POST" and formulario.is_valid():
        try:
            asignar_tutor(proyecto_obj, formulario.cleaned_data["tutor"], request.user, formulario.cleaned_data.get("motivo_cambio"), request)
            messages.success(request, "Tutor asignado correctamente.")
            return redirect("titulacion:proyecto_detail", pk=pk)
        except (PermissionDenied, ValidationError) as error:
            _mensaje_validacion(request, error)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Asignar tutor", "page_title": "Asignar tutor", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def cambio_tutor_create(request, proyecto_pk):
    proyecto_obj = obtener_proyecto_visible(request.user, proyecto_pk)
    if not puede_solicitar_cambio_tutor(request.user, proyecto_obj):
        raise PermissionDenied("No puede solicitar un cambio de tutor.")
    asignacion = proyecto_obj.asignaciones_tutor.select_related(
        "tutor__usuario"
    ).get(estado=EstadoAsignacion.ACTIVO)
    formulario = SolicitudCambioTutorForm(
        request.POST or None,
        proyecto=proyecto_obj,
        asignacion_actual=asignacion,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            solicitar_cambio_tutor(
                proyecto_obj,
                formulario.cleaned_data["tutor_propuesto"],
                formulario.cleaned_data["motivo"],
                request.user,
                request,
            )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Solicitud de cambio de tutor registrada.")
            return redirect("titulacion:proyecto_detail", pk=proyecto_pk)
    return render(
        request,
        "titulacion/cambio_tutor_form.html",
        {
            "form": formulario,
            "proyecto": proyecto_obj,
            "asignacion": asignacion,
            "page_title": "Solicitar cambio de tutor",
            "active_page": "proyecto",
        },
    )


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def cambio_tutor_resolver(request, pk):
    solicitud = get_object_or_404(
        SolicitudCambioTutor.objects.select_related(
            "proyecto__maestrante__programa",
            "asignacion_actual__tutor__usuario",
            "tutor_propuesto__usuario",
            "solicitado_por",
        ),
        pk=pk,
        proyecto__in=proyectos_visibles(request.user),
    )
    if (
        rol_usuario(request.user) != "coordinador"
        or not usuario_tiene_permiso(request.user, "CAMBIO_TUTOR_GESTIONAR")
    ):
        raise PermissionDenied("No puede resolver este cambio de tutor.")
    formulario = ResolucionCambioTutorForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            resolver_cambio_tutor(
                solicitud,
                request.user,
                formulario.cleaned_data["decision"] == "aprobar",
                formulario.cleaned_data.get("observaciones"),
                request,
            )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Solicitud de cambio de tutor resuelta.")
            return redirect(
                "titulacion:proyecto_detail", pk=solicitud.proyecto_id
            )
    return render(
        request,
        "titulacion/cambio_tutor_resolver.html",
        {
            "form": formulario,
            "solicitud": solicitud,
            "page_title": "Resolver cambio de tutor",
            "active_page": "proyecto",
        },
    )


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def archivo_create(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not (
        puede_editar_proyecto(request.user, proyecto_obj)
        and usuario_tiene_permiso(request.user, "ARCHIVO_SUBIR")
    ):
        raise PermissionDenied("No puede registrar archivos en este proyecto.")
    formulario = ArchivoProyectoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        referencia = None
        try:
            subido = formulario.cleaned_data["archivo"]
            tipo = formulario.cleaned_data["tipo_archivo"]
            permitidas = {
                "word": {"doc", "docx"},
                "pdf": {"pdf"},
                "resolucion": {"pdf"},
                "anexo": {"doc", "docx", "pdf"},
            }
            datos = guardar_archivo(
                subido,
                categoria="archivos-proyecto",
                proyecto_id=proyecto_obj.pk,
                extensiones=permitidas[tipo],
                limite_bytes=MAX_DOCUMENTO,
            )
            referencia = datos["referencia"]
            with transaction.atomic():
                archivo = ArchivoProyecto.objects.create(
                    proyecto=proyecto_obj,
                    tipo_archivo=tipo,
                    nombre_original=datos["nombre_original"],
                    ruta_archivo=referencia,
                    extension=datos["extension"],
                    tamano_bytes=datos["tamano_bytes"],
                    subido_por=request.user,
                )
                registrar_solicitud_aprobacion(
                    proyecto=proyecto_obj,
                    tipo="archivo_proyecto",
                    tabla="archivos_proyecto",
                    registro_id=archivo.pk,
                )
                registrar_evento(request, accion="subir_archivo_proyecto", tabla="archivos_proyecto", registro_id=archivo.pk, descripcion="Se subió un archivo privado del proyecto.")
            messages.success(request, "Archivo subido y enviado a revisión.")
            return redirect("titulacion:proyecto_detail", pk=pk)
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
        except Exception:
            if referencia:
                eliminar_archivo(referencia)
            raise
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Subir archivo", "nota": "El documento se almacena de forma privada y solo puede descargarse desde un expediente autorizado.", "page_title": "Subir archivo", "active_page": "proyecto"})


@usuario_activo_required
def archivo_download(request, pk):
    archivo = get_object_or_404(
        ArchivoProyecto.objects.select_related("proyecto"),
        pk=pk,
        proyecto__in=proyectos_visibles(request.user),
    )
    return respuesta_descarga(archivo.ruta_archivo, archivo.nombre_original)


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def archivo_revisar(request, pk):
    archivo = get_object_or_404(
        ArchivoProyecto.objects.select_related("proyecto"),
        pk=pk,
        proyecto__in=proyectos_visibles(request.user),
    )
    if not puede_revisar_archivo(request.user, archivo):
        raise PermissionDenied("No puede revisar este archivo.")
    formulario = RevisionArchivoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        resolver_revision_archivo(
            archivo,
            request.user,
            formulario.cleaned_data["estado"],
            formulario.cleaned_data["observaciones"],
            request,
        )
        messages.success(request, "Revisión del archivo registrada.")
        return redirect("titulacion:proyecto_detail", pk=archivo.proyecto_id)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": f"Revisar {archivo.nombre_original}", "page_title": "Revisar archivo", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def tutoria_create(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not puede_gestionar_programacion(request.user, proyecto_obj):
        raise PermissionDenied("No puede programar tutorías para este proyecto.")
    asignacion = proyecto_obj.asignaciones_tutor.filter(estado=EstadoAsignacion.ACTIVO).first()
    if not asignacion:
        messages.error(request, "Asigne un tutor antes de programar tutorías.")
        return redirect("titulacion:proyecto_detail", pk=pk)
    if proyecto_obj.tutorias.count() >= 8:
        messages.info(request, "El proyecto ya tiene las ocho tutorías programadas.")
        return redirect("titulacion:proyecto_detail", pk=pk)
    formulario = TutoriaForm(request.POST or None, proyecto=proyecto_obj)
    if request.method == "POST" and formulario.is_valid():
        try:
            programar_tutoria(
                proyecto_obj,
                asignacion.tutor,
                formulario.cleaned_data,
                request.user,
                request,
            )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Tutoría programada.")
            return redirect("titulacion:proyecto_detail", pk=pk)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Programar tutoría", "page_title": "Programar tutoría", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def tutoria_registrar(request, pk):
    tutoria = get_object_or_404(Tutoria.objects.select_related("proyecto", "tutor__usuario"), pk=pk, proyecto__in=proyectos_visibles(request.user))
    if not puede_registrar_sesion(request.user, tutoria):
        raise PermissionDenied("No puede registrar el resultado de esta tutoría.")
    formulario = RegistroTutoriaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            tutoria.estado = formulario.cleaned_data["estado"]
            tutoria.observacion_general = formulario.cleaned_data["observacion_general"] or None
            tutoria.save()
            AsistenciaTutoria.objects.update_or_create(
                tutoria=tutoria,
                defaults={
                    "asistio_tutor": formulario.cleaned_data["asistio_tutor"],
                    "asistio_maestrante": formulario.cleaned_data["asistio_maestrante"],
                    "registrado_por": request.user,
                    "observaciones": formulario.cleaned_data["observaciones_asistencia"] or None,
                },
            )
            registrar_evento(request, accion="registrar_resultado_tutoria", tabla="tutorias", registro_id=tutoria.pk, descripcion=f"Tutoría registrada como {tutoria.estado}.")
        messages.success(request, "Resultado y asistencia registrados.")
        return redirect("titulacion:proyecto_detail", pk=tutoria.proyecto_id)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": f"Registrar tutoría {tutoria.numero_tutoria}", "page_title": "Registrar tutoría", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def reprogramacion_create(request, pk):
    tutoria = get_object_or_404(Tutoria.objects.select_related("proyecto", "tutor__usuario"), pk=pk, proyecto__in=proyectos_visibles(request.user))
    if rol_usuario(request.user) not in {"maestrante", "tutor", "coordinador"}:
        raise PermissionDenied("No puede solicitar una reprogramación.")
    formulario = ReprogramacionTutoriaForm(request.POST or None, tutoria=tutoria)
    if request.method == "POST" and formulario.is_valid():
        try:
            solicitar_reprogramacion(
                tutoria,
                formulario.cleaned_data,
                request.user,
                request,
            )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Solicitud de reprogramación registrada.")
            return redirect("titulacion:proyecto_detail", pk=tutoria.proyecto_id)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Solicitar reprogramación", "page_title": "Reprogramar tutoría", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def reprogramacion_resolver(request, pk):
    reprogramacion = get_object_or_404(ReprogramacionTutoria.objects.select_related("tutoria__proyecto"), pk=pk, tutoria__proyecto__in=proyectos_visibles(request.user))
    if (
        rol_usuario(request.user) != "coordinador"
        or not usuario_tiene_permiso(request.user, "REPROGRAMACION_GESTIONAR")
    ):
        raise PermissionDenied("No puede resolver esta reprogramación.")
    formulario = ResolucionCambioTutorForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            resolver_reprogramacion(
                reprogramacion,
                request.user,
                formulario.cleaned_data["decision"] == "aprobar",
                request,
                formulario.cleaned_data.get("observaciones"),
            )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Reprogramación resuelta.")
            return redirect(
                "titulacion:proyecto_detail",
                pk=reprogramacion.tutoria.proyecto_id,
            )
    return render(
        request,
        "titulacion/reprogramacion_resolver.html",
        {
            "form": formulario,
            "reprogramacion": reprogramacion,
            "page_title": "Resolver reprogramación",
            "active_page": "proyecto",
        },
    )


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def grabacion_create(request, pk):
    tutoria = get_object_or_404(Tutoria.objects.select_related("proyecto", "tutor__usuario"), pk=pk, proyecto__in=proyectos_visibles(request.user))
    if rol_usuario(request.user) != "tutor" or tutoria.tutor.usuario_id != request.user.pk or not usuario_tiene_permiso(request.user, "GRABACION_REGISTRAR"):
        raise PermissionDenied("Solo el tutor asignado puede registrar la grabación.")
    formulario = GrabacionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        referencia = None
        try:
            tipo = formulario.cleaned_data["tipo_grabacion"]
            datos = None
            if tipo == "archivo":
                datos = guardar_archivo(
                    formulario.cleaned_data["archivo"],
                    categoria="grabaciones",
                    proyecto_id=tutoria.proyecto_id,
                    extensiones={"mp4", "webm", "mp3"},
                    limite_bytes=MAX_GRABACION,
                )
                referencia = datos["referencia"]
            with transaction.atomic():
                grabacion = Grabacion.objects.create(
                    tutoria=tutoria,
                    tipo_grabacion=tipo,
                    enlace_grabacion=formulario.cleaned_data.get("enlace_grabacion") or None,
                    ruta_archivo=referencia,
                    nombre_original=datos["nombre_original"] if datos else None,
                    extension=datos["extension"] if datos else None,
                    tamano_bytes=datos["tamano_bytes"] if datos else None,
                    registrado_por=request.user,
                )
                registrar_evento(request, accion="registrar_grabacion", tabla="grabaciones", registro_id=grabacion.pk, descripcion="Se registró una grabación privada de tutoría.")
            messages.success(request, "Grabación registrada.")
            return redirect("titulacion:proyecto_detail", pk=tutoria.proyecto_id)
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
        except Exception:
            if referencia:
                eliminar_archivo(referencia)
            raise
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Registrar grabación", "page_title": "Grabación", "active_page": "proyecto"})


@usuario_activo_required
def grabacion_download(request, pk):
    grabacion = get_object_or_404(
        Grabacion.objects.select_related("tutoria__proyecto"),
        pk=pk,
        tutoria__proyecto__in=proyectos_visibles(request.user),
        tipo_grabacion="archivo",
    )
    nombre = grabacion.nombre_original or f"grabacion-{grabacion.pk}.{grabacion.extension or 'bin'}"
    return respuesta_descarga(grabacion.ruta_archivo, nombre)


@usuario_activo_required
def grabacion_enlace(request, pk):
    grabacion = get_object_or_404(
        Grabacion.objects.select_related("tutoria__proyecto"),
        pk=pk,
        tutoria__proyecto__in=proyectos_visibles(request.user),
        tipo_grabacion="enlace",
    )
    enlace = str(grabacion.enlace_grabacion or "")
    if urlparse(enlace).scheme != "https":
        raise PermissionDenied("El enlace de grabación no es seguro.")
    return redirect(enlace)


@usuario_activo_required
def resolucion_download(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not proyecto_obj.documento_resolucion_url:
        raise PermissionDenied("El proyecto no tiene un documento de resolución.")
    return respuesta_descarga(
        proyecto_obj.documento_resolucion_url,
        f"resolucion-proyecto-{proyecto_obj.pk}.pdf",
    )


@usuario_activo_required
def articulo(request):
    proyectos = proyectos_visibles(request.user).filter(
        modalidad=ModalidadProyecto.ARTICULO
    )
    articulos = Articulo.objects.select_related("proyecto", "proyecto__maestrante__usuario").filter(proyecto__in=proyectos, esta_activo=True)
    return render(request, "titulacion/articulo.html", {"articulos": articulos, "proyectos": proyectos, "rol_actual": rol_usuario(request.user), "page_title": "Artículos", "page_subtitle": "Artículos visibles para su rol", "active_page": "articulo"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def articulo_edit(request, proyecto_pk):
    proyecto_obj = obtener_proyecto_visible(request.user, proyecto_pk)
    articulo_obj = proyecto_obj.articulos.filter(esta_activo=True).first()
    if not puede_editar_articulo(request.user, proyecto_obj):
        raise PermissionDenied(
            "Este proyecto no usa artículo científico o no puede editarlo."
        )
    formulario = ArticuloForm(request.POST or None, instance=articulo_obj)
    if request.method == "POST" and formulario.is_valid():
        articulo_obj = formulario.save(commit=False)
        articulo_obj.proyecto = proyecto_obj
        articulo_obj.save()
        registrar_evento(request, accion="editar_articulo", tabla="articulos", registro_id=articulo_obj.pk, descripcion="Se guardó el avance del artículo.")
        messages.success(request, "Artículo actualizado.")
        return redirect("titulacion:articulo")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Editar artículo", "page_title": "Editar artículo", "active_page": "articulo"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def articulo_revisar(request, pk):
    articulo_obj = get_object_or_404(Articulo.objects.select_related("proyecto"), pk=pk, proyecto__in=proyectos_visibles(request.user))
    if not puede_revisar_articulo(request.user, articulo_obj.proyecto):
        raise PermissionDenied("No puede revisar este artículo.")
    formulario = RevisionArticuloForm(request.POST or None, instance=articulo_obj)
    if request.method == "POST" and formulario.is_valid():
        articulo_obj = formulario.save()
        registrar_evento(request, accion="revisar_articulo", tabla="articulos", registro_id=articulo_obj.pk, descripcion=f"Artículo revisado: {articulo_obj.estado}.")
        messages.success(request, "Revisión del artículo registrada.")
        return redirect("titulacion:articulo")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Revisar artículo", "page_title": "Revisar artículo", "active_page": "articulo"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def cambio_tema_create(request, proyecto_pk):
    proyecto_obj = obtener_proyecto_visible(request.user, proyecto_pk)
    if not puede_solicitar_cambio_tema(request.user, proyecto_obj):
        raise PermissionDenied("No puede solicitar un cambio de tema.")
    formulario = SolicitudCambioTemaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            with transaction.atomic():
                solicitud = formulario.save(commit=False)
                solicitud.proyecto = proyecto_obj
                solicitud.tema_actual = proyecto_obj.tema
                solicitud.solicitado_por = request.user
                solicitud.save()
                proceso = iniciar_proceso_cambio(
                    solicitud,
                    TipoProcesoAprobacion.CAMBIO_TEMA,
                    request.user,
                    request,
                )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Solicitud enviada al proceso formal de aprobación.")
            return redirect("titulacion:proceso_aprobacion_detail", pk=proceso.pk)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Solicitar cambio de tema", "page_title": "Cambio de tema", "active_page": "proyecto"})


@usuario_activo_required
@require_POST
def cambio_tema_resolver(request, pk):
    solicitud = get_object_or_404(SolicitudCambioTema.objects.select_related("proyecto"), pk=pk, proyecto__in=proyectos_visibles(request.user))
    proceso = ProcesoAprobacion.objects.filter(
        tipo=TipoProcesoAprobacion.CAMBIO_TEMA,
        referencia_tabla="solicitudes_cambio_tema",
        referencia_id=solicitud.pk,
    ).order_by("-fecha_creacion").first()
    if not proceso:
        raise PermissionDenied("La solicitud no tiene un proceso formal asociado.")
    return redirect("titulacion:proceso_aprobacion_detail", pk=proceso.pk)


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def cambio_modalidad_create(request, proyecto_pk):
    proyecto_obj = obtener_proyecto_visible(request.user, proyecto_pk)
    if not puede_solicitar_cambio_modalidad(request.user, proyecto_obj):
        raise PermissionDenied("No puede solicitar un cambio de modalidad.")
    formulario = SolicitudCambioModalidadForm(
        request.POST or None,
        proyecto=proyecto_obj,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            with transaction.atomic():
                solicitud = formulario.save(commit=False)
                solicitud.proyecto = proyecto_obj
                solicitud.modalidad_actual = proyecto_obj.modalidad
                solicitud.solicitado_por = request.user
                solicitud.save()
                proceso = iniciar_proceso_cambio(
                    solicitud,
                    TipoProcesoAprobacion.CAMBIO_MODALIDAD,
                    request.user,
                    request,
                )
        except (PermissionDenied, ValidationError) as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Solicitud enviada al proceso formal de aprobación.")
            return redirect("titulacion:proceso_aprobacion_detail", pk=proceso.pk)
    return render(
        request,
        "titulacion/form.html",
        {
            "form": formulario,
            "titulo": "Solicitar cambio de modalidad",
            "page_title": "Cambio de modalidad",
            "active_page": "proyecto",
        },
    )


@usuario_activo_required
@require_POST
def cambio_modalidad_resolver(request, pk):
    solicitud = get_object_or_404(
        SolicitudCambioModalidad.objects.select_related(
            "proyecto", "proyecto__maestrante__programa"
        ),
        pk=pk,
        proyecto__in=proyectos_visibles(request.user),
    )
    proceso = ProcesoAprobacion.objects.filter(
        tipo=TipoProcesoAprobacion.CAMBIO_MODALIDAD,
        referencia_tabla="solicitudes_cambio_modalidad",
        referencia_id=solicitud.pk,
    ).order_by("-fecha_creacion").first()
    if not proceso:
        raise PermissionDenied("La solicitud no tiene un proceso formal asociado.")
    return redirect("titulacion:proceso_aprobacion_detail", pk=proceso.pk)


@usuario_activo_required
def proceso_aprobacion_detail(request, pk):
    proceso = obtener_proceso_visible(request.user, pk)
    pasos = list(proceso.pasos.select_related("resuelto_por").all())
    documentos = proceso.documentos.select_related("archivo").all()
    paso_actual = next((paso for paso in pasos if paso.estado == "activo"), None)
    puede_resolver = bool(
        paso_actual and puede_resolver_paso(request.user, paso_actual)
    )
    formulario = (
        RevisionPasoAprobacionForm(
            permite_observar=proceso.tipo == TipoProcesoAprobacion.PROYECTO
        )
        if puede_resolver
        else None
    )
    solicitud = None
    if proceso.tipo == TipoProcesoAprobacion.CAMBIO_TEMA:
        solicitud = SolicitudCambioTema.objects.filter(pk=proceso.referencia_id).first()
    elif proceso.tipo == TipoProcesoAprobacion.CAMBIO_MODALIDAD:
        solicitud = SolicitudCambioModalidad.objects.filter(pk=proceso.referencia_id).first()
    return render(
        request,
        "titulacion/proceso_aprobacion_detail.html",
        {
            "proceso": proceso,
            "pasos": pasos,
            "documentos": documentos,
            "paso_actual": paso_actual,
            "puede_resolver": puede_resolver,
            "form": formulario,
            "solicitud": solicitud,
            "rol_actual": rol_usuario(request.user),
            "page_title": "Proceso de aprobación",
            "page_subtitle": proceso.get_tipo_display(),
            "active_page": "aprobaciones",
        },
    )


@usuario_activo_required
@require_POST
def paso_aprobacion_resolver(request, pk):
    paso = get_object_or_404(
        PasoAprobacion.objects.select_related(
            "proceso",
            "proceso__proyecto__maestrante__programa",
        ),
        pk=pk,
        proceso__in=procesos_visibles(request.user),
    )
    if not puede_resolver_paso(request.user, paso):
        raise PermissionDenied("No puede resolver esta etapa.")
    formulario = RevisionPasoAprobacionForm(
        request.POST,
        permite_observar=paso.proceso.tipo == TipoProcesoAprobacion.PROYECTO,
    )
    if formulario.is_valid():
        try:
            proceso = resolver_paso(
                paso,
                request.user,
                formulario.cleaned_data["decision"],
                formulario.cleaned_data["observaciones"],
                request,
            )
        except (PermissionDenied, ValidationError) as error:
            _mensaje_validacion(request, error)
        else:
            messages.success(request, "Etapa de aprobación resuelta.")
            return redirect("titulacion:proceso_aprobacion_detail", pk=proceso.pk)
    else:
        for errores in formulario.errors.values():
            for error in errores:
                messages.error(request, error)
    return redirect("titulacion:proceso_aprobacion_detail", pk=paso.proceso_id)


@usuario_activo_required
def aprobaciones(request):
    consulta = procesos_visibles(request.user).prefetch_related("pasos")
    return render(
        request,
        "titulacion/aprobaciones.html",
        {
            "procesos": consulta,
            "pendientes": consulta.filter(estado="en_curso").count(),
            "aprobadas": consulta.filter(estado="aprobado").count(),
            "observadas": consulta.filter(estado="observado").count(),
            "rechazadas": consulta.filter(estado="rechazado").count(),
            "rol_actual": rol_usuario(request.user),
            "page_title": "Aprobaciones",
            "page_subtitle": "Procesos formales y decisiones por etapa",
            "active_page": "aprobaciones",
        },
    )


@usuario_activo_required
def requerimientos(request):
    return render(request, "titulacion/requerimientos.html", {"page_title": "Requerimientos", "page_subtitle": "Requerimientos del módulo", "active_page": "requerimientos"})


@permiso_required("MODALIDAD_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def modalidades_configuracion(request):
    _exigir_rol(request, "coordinador", "administrador_desarrollador")
    programas = Programa.objects.filter(estado="activo")
    if rol_usuario(request.user) == "coordinador":
        programas = programas.filter(coordinador=request.user)
    programas = programas.order_by("nombre")

    programa_id = request.POST.get("programa") or request.GET.get("programa")
    programa_obj = (
        programas.filter(pk=programa_id).first()
        if str(programa_id or "").isdigit()
        else programas.first()
    )
    configuracion = (
        ConfiguracionModalidadPrograma.objects.filter(programa=programa_obj).first()
        if programa_obj
        else None
    )
    formulario = ConfiguracionModalidadProgramaForm(
        request.POST or None,
        instance=configuracion,
        usuario=request.user,
        initial={"programa": programa_obj} if programa_obj else None,
    )
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            configuracion = formulario.save(commit=False)
            if not configuracion.pk:
                configuracion.creado_por = request.user
            configuracion.actualizado_por = request.user
            configuracion.full_clean()
            configuracion.save()
            registrar_evento(
                request,
                accion="configurar_modalidad_programa",
                tabla="configuraciones_modalidad_programa",
                registro_id=configuracion.pk,
                descripcion=f"Se configuró la modalidad adicional del programa {configuracion.programa.codigo}.",
            )
        messages.success(request, "Modalidad del programa actualizada.")
        return redirect(f"{request.path}?programa={configuracion.programa_id}")

    configuraciones = ConfiguracionModalidadPrograma.objects.select_related(
        "programa", "actualizado_por"
    ).filter(programa__in=programas)
    return render(
        request,
        "titulacion/modalidades_configuracion.html",
        {
            "form": formulario,
            "programas": programas,
            "programa_seleccionado": programa_obj,
            "configuraciones": configuraciones,
            "page_title": "Modalidades por programa",
            "page_subtitle": "Configuración controlada de la opción Otra",
            "active_page": "modalidades_configuracion",
        },
    )


@permiso_required("TUTOR_VER")
def tutores_list(request):
    _exigir_rol(request, "coordinador", "supervisor")
    consulta = _tutores_visibles(request.user)
    busqueda = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    if busqueda:
        consulta = consulta.filter(Q(usuario__nombres__icontains=busqueda) | Q(usuario__apellidos__icontains=busqueda) | Q(usuario__correo__icontains=busqueda) | Q(especialidad__icontains=busqueda))
    if estado in {valor for valor, _ in EstadoTutor.choices}:
        consulta = consulta.filter(estado=estado)
    else:
        estado = ""
    consulta = consulta.order_by("usuario__apellidos", "usuario__nombres", "id")
    return render(request, "titulacion/tutores_list.html", {"pagina": Paginator(consulta, 20).get_page(request.GET.get("page")), "busqueda": busqueda, "estado_seleccionado": estado, "estados": EstadoTutor.choices, "puede_crear": rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "TUTOR_CREAR"), "puede_editar": rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "TUTOR_EDITAR"), "page_title": "Tutores", "page_subtitle": "Perfiles académicos de tutores", "active_page": "tutores"})


@permiso_required("TUTOR_CREAR")
@require_http_methods(["GET", "POST"])
def tutor_create(request):
    _exigir_rol(request, "coordinador")
    formulario = TutorForm(request.POST or None, usuario_actual=request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            tutor = formulario.save()
            registrar_evento(request, accion="crear_tutor", tabla="tutores", registro_id=tutor.pk, descripcion="Se registró el perfil académico del tutor.")
        messages.success(request, "Tutor registrado.")
        return redirect("titulacion:tutor_detail", pk=tutor.pk)
    return render(request, "titulacion/tutor_form.html", {"form": formulario, "hay_usuarios_disponibles": formulario.fields["usuario"].queryset.exists(), "modo": "crear", "page_title": "Registrar tutor", "page_subtitle": "Vincular cuenta institucional", "active_page": "tutores"})


@usuario_activo_required
def tutor_detail(request, pk):
    tutor = get_object_or_404(_tutores_visibles(request.user), pk=pk)
    rol = rol_usuario(request.user)
    es_propio = rol == "tutor" and tutor.usuario_id == request.user.pk
    puede_consultar = es_propio or (
        rol in {"coordinador", "supervisor"}
        and usuario_tiene_permiso(request.user, "TUTOR_VER")
    )
    if not puede_consultar:
        raise PermissionDenied("No puede consultar este perfil de tutor.")
    return render(
        request,
        "titulacion/tutor_detail.html",
        {
            "tutor": tutor,
            "puede_editar": rol == "coordinador" and usuario_tiene_permiso(request.user, "TUTOR_EDITAR"),
            "puede_disponibilidad": (es_propio or rol == "coordinador") and usuario_tiene_permiso(request.user, "TUTOR_DISPONIBILIDAD_GESTIONAR"),
            "asignaciones_activas": tutor.asignaciones.select_related("proyecto__maestrante__usuario").filter(estado=EstadoAsignacion.ACTIVO),
            "page_title": "Detalle de tutor",
            "page_subtitle": "Información institucional y académica",
            "active_page": "tutores",
        },
    )


@permiso_required("TUTOR_EDITAR")
@require_http_methods(["GET", "POST"])
def tutor_update(request, pk):
    _exigir_rol(request, "coordinador")
    tutor = get_object_or_404(_tutores_visibles(request.user), pk=pk)
    formulario = TutorForm(
        request.POST or None,
        instance=tutor,
        usuario_actual=request.user,
    )
    if request.method == "POST" and formulario.is_valid():
        tutor = formulario.save()
        registrar_evento(request, accion="editar_tutor", tabla="tutores", registro_id=tutor.pk, descripcion="Se actualizó el perfil del tutor.")
        messages.success(request, "Tutor actualizado.")
        return redirect("titulacion:tutor_detail", pk=tutor.pk)
    return render(request, "titulacion/tutor_form.html", {"form": formulario, "tutor": tutor, "modo": "editar", "page_title": "Editar tutor", "page_subtitle": "Actualizar datos académicos", "active_page": "tutores"})


@permiso_required("TUTOR_EDITAR")
@require_POST
def tutor_toggle_estado(request, pk):
    _exigir_rol(request, "coordinador")
    tutor = get_object_or_404(_tutores_visibles(request.user), pk=pk)
    reactivar = tutor.estado == EstadoTutor.INACTIVO
    if not reactivar and tutor.asignaciones.filter(
        estado=EstadoAsignacion.ACTIVO
    ).exists():
        messages.error(
            request,
            "No puede desactivar un tutor con proyectos activos. Gestione primero sus cambios de tutor.",
        )
        return redirect("titulacion:tutor_detail", pk=tutor.pk)
    tutor.estado = EstadoTutor.DISPONIBLE if reactivar else EstadoTutor.INACTIVO
    tutor.save(update_fields=("estado", "fecha_actualizacion"))
    registrar_evento(request, accion="reactivar_tutor" if reactivar else "desactivar_tutor", tabla="tutores", registro_id=tutor.pk, descripcion="Se cambió el estado del perfil del tutor.")
    messages.success(request, "Estado del tutor actualizado.")
    return redirect("titulacion:tutor_detail", pk=tutor.pk)


def _puede_gestionar_disponibilidad(usuario, tutor):
    rol = rol_usuario(usuario)
    return (
        usuario_tiene_permiso(usuario, "TUTOR_DISPONIBILIDAD_GESTIONAR")
        and (
            (rol == "tutor" and tutor.usuario_id == usuario.pk)
            or rol == "coordinador"
        )
    )


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def tutor_disponibilidad_create(request, pk):
    tutor = get_object_or_404(_tutores_visibles(request.user), pk=pk)
    if not _puede_gestionar_disponibilidad(request.user, tutor):
        raise PermissionDenied("No puede gestionar esta disponibilidad.")
    formulario = DisponibilidadTutorForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        cruce = tutor.disponibilidades.filter(
            dia_semana=datos["dia_semana"],
            esta_activa=True,
            hora_inicio__lt=datos["hora_fin"],
            hora_fin__gt=datos["hora_inicio"],
        ).exists()
        if cruce:
            formulario.add_error(None, "El bloque se cruza con otra disponibilidad.")
        else:
            disponibilidad = formulario.save(commit=False)
            disponibilidad.tutor = tutor
            disponibilidad.full_clean()
            disponibilidad.save()
            registrar_evento(
                request,
                accion="crear_disponibilidad_tutor",
                tabla="disponibilidades_tutor",
                registro_id=disponibilidad.pk,
                descripcion="Se registró un bloque semanal de disponibilidad.",
            )
            messages.success(request, "Disponibilidad registrada.")
            return redirect("titulacion:tutor_detail", pk=tutor.pk)
    return render(
        request,
        "titulacion/form.html",
        {
            "form": formulario,
            "titulo": f"Disponibilidad de {tutor.usuario.nombre_completo}",
            "page_title": "Registrar disponibilidad",
            "active_page": "tutores",
        },
    )


@usuario_activo_required
@require_POST
def tutor_disponibilidad_toggle(request, pk):
    disponibilidad = get_object_or_404(
        DisponibilidadTutor.objects.select_related("tutor__usuario"), pk=pk
    )
    if not _puede_gestionar_disponibilidad(
        request.user, disponibilidad.tutor
    ) or not _tutores_visibles(request.user).filter(
        pk=disponibilidad.tutor_id
    ).exists():
        raise PermissionDenied("No puede gestionar esta disponibilidad.")
    disponibilidad.esta_activa = not disponibilidad.esta_activa
    disponibilidad.save(update_fields=("esta_activa", "fecha_actualizacion"))
    registrar_evento(
        request,
        accion="cambiar_disponibilidad_tutor",
        tabla="disponibilidades_tutor",
        registro_id=disponibilidad.pk,
        descripcion="Se cambió el estado de una disponibilidad semanal.",
    )
    messages.success(request, "Disponibilidad actualizada.")
    return redirect("titulacion:tutor_detail", pk=disponibilidad.tutor_id)


@permiso_required("CALENDARIO_TUTORIAS_VER")
def calendario_tutorias(request):
    rol = rol_usuario(request.user)
    consulta = Tutoria.objects.select_related(
        "proyecto__maestrante__usuario",
        "proyecto__maestrante__programa",
        "tutor__usuario",
    )
    if rol == "maestrante":
        consulta = consulta.filter(proyecto__maestrante__usuario_id=request.user.pk)
    elif rol == "tutor":
        consulta = consulta.filter(tutor__usuario_id=request.user.pk)
    elif rol == "coordinador":
        consulta = consulta.filter(
            proyecto__maestrante__programa__coordinador_id=request.user.pk
        )
    elif rol != "supervisor":
        raise PermissionDenied("No puede consultar el calendario.")
    desde = request.GET.get("desde", "").strip()
    hasta = request.GET.get("hasta", "").strip()
    try:
        fecha_desde = date.fromisoformat(desde) if desde else None
        fecha_hasta = date.fromisoformat(hasta) if hasta else None
    except ValueError:
        fecha_desde = fecha_hasta = None
        desde = hasta = ""
    if fecha_desde:
        consulta = consulta.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        consulta = consulta.filter(fecha__lte=fecha_hasta)
    consulta = consulta.order_by("fecha", "hora_inicio", "numero_tutoria")
    hoy = timezone.localdate()
    estadisticas = consulta.aggregate(
        total=Count("id"),
        futuras=Count("id", filter=Q(fecha__gte=hoy, estado__in=[EstadoTutoria.PROGRAMADA, EstadoTutoria.REPROGRAMADA])),
        realizadas=Count("id", filter=Q(estado=EstadoTutoria.REALIZADA)),
        reprogramadas=Count("id", filter=Q(estado=EstadoTutoria.REPROGRAMADA)),
    )
    return render(
        request,
        "titulacion/calendario_tutorias.html",
        {
            "tutorias": consulta,
            "estadisticas": estadisticas,
            "desde": desde,
            "hasta": hasta,
            "hoy": hoy,
            "page_title": "Calendario de tutorías",
            "page_subtitle": "Agenda académica según su alcance",
            "active_page": "calendario_tutorias",
        },
    )


# ---------------------------------------------------------------------------
# Fase 7A — Onboarding obligatorio del maestrante
# ---------------------------------------------------------------------------


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def onboarding_gate(request):
    _exigir_rol(request, "maestrante")
    maestrante = getattr(request.user, "perfil_maestrante", None)
    if not maestrante:
        raise PermissionDenied("Su cuenta no tiene un expediente de maestrante asociado.")

    onboarding = obtener_onboarding_maestrante(maestrante)
    elegible = maestrante_es_elegible_onboarding(maestrante)

    if request.method == "POST":
        if not onboarding:
            if not elegible:
                raise PermissionDenied(
                    "Aún no cumple el módulo mínimo requerido para iniciar el onboarding."
                )
            onboarding = iniciar_onboarding(request.user)

        opciones = tuple(
            (configurada.tipo_modalidad, configurada.nombre)
            for configurada in modalidades_configuradas_activas(maestrante.programa)
        ) or modalidades_disponibles(maestrante.programa)
        formulario = SeleccionModalidadOnboardingForm(request.POST, opciones=opciones)
        if formulario.is_valid():
            try:
                completar_onboarding(request.user, formulario.cleaned_data["modalidad"])
                registrar_evento(
                    request,
                    accion="completar_onboarding",
                    tabla="onboarding_maestrantes",
                    registro_id=onboarding.pk,
                    descripcion="El maestrante completó el onboarding y seleccionó modalidad.",
                )
                messages.success(request, "Onboarding completado. Ya puede continuar con su seguimiento.")
                return redirect("seguimiento:dashboard")
            except (PermissionDenied, ValidationError) as error:
                _mensaje_validacion(request, error)
    else:
        opciones = tuple(
            (configurada.tipo_modalidad, configurada.nombre)
            for configurada in modalidades_configuradas_activas(maestrante.programa)
        ) or modalidades_disponibles(maestrante.programa)
        formulario = SeleccionModalidadOnboardingForm(opciones=opciones)

    return render(
        request,
        "titulacion/onboarding.html",
        {
            "maestrante": maestrante,
            "onboarding": onboarding,
            "elegible": elegible,
            "modulo_minimo": 5,
            "form": formulario,
            "page_title": "Onboarding de titulación",
            "page_subtitle": "Selección obligatoria de modalidad antes de iniciar el seguimiento",
            "active_page": "onboarding",
        },
    )


@usuario_activo_required
@require_POST
def onboarding_iniciar(request):
    _exigir_rol(request, "maestrante")
    try:
        iniciar_onboarding(request.user)
    except (PermissionDenied, ValidationError) as error:
        _mensaje_validacion(request, error)
    return redirect("titulacion:onboarding_gate")


# ---------------------------------------------------------------------------
# Fase 7B — Modalidades configuradas y sus etapas (supervisor/coordinador/admin)
# ---------------------------------------------------------------------------


@permiso_required("MODALIDAD_CONFIGURAR")
def modalidades_configuradas_list(request):
    consulta = ModalidadConfigurada.objects.select_related("programa").order_by(
        "programa__nombre", "tipo_modalidad"
    )
    if rol_usuario(request.user) == "coordinador":
        consulta = consulta.filter(Q(programa__isnull=True) | Q(programa__coordinador=request.user))
    return render(
        request,
        "titulacion/modalidades_configuradas_list.html",
        {
            "modalidades": consulta,
            "puede_evaluar": False,
            "page_title": "Modalidades configuradas",
            "page_subtitle": "Modalidades base y por programa, con sus etapas",
            "active_page": "modalidades_configuradas",
        },
    )


@permiso_required("MODALIDAD_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def modalidad_configurada_create(request):
    formulario = ModalidadConfiguradaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        modalidad = formulario.save(commit=False)
        modalidad.creado_por = request.user
        modalidad.actualizado_por = request.user
        modalidad.full_clean()
        modalidad.save()
        registrar_evento(request, accion="crear_modalidad_configurada", tabla="modalidades_configuradas", registro_id=modalidad.pk, descripcion="Se creó una modalidad configurada.")
        messages.success(request, "Modalidad creada.")
        return redirect("titulacion:modalidades_configuradas_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Crear modalidad", "page_title": "Crear modalidad", "active_page": "modalidades_configuradas"})


@permiso_required("MODALIDAD_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def modalidad_configurada_update(request, pk):
    modalidad = get_object_or_404(ModalidadConfigurada, pk=pk)
    formulario = ModalidadConfiguradaForm(request.POST or None, instance=modalidad, usuario=request.user)
    if request.method == "POST" and formulario.is_valid():
        modalidad = formulario.save(commit=False)
        modalidad.actualizado_por = request.user
        modalidad.full_clean()
        modalidad.save()
        registrar_evento(request, accion="editar_modalidad_configurada", tabla="modalidades_configuradas", registro_id=modalidad.pk, descripcion="Se editó una modalidad configurada.")
        messages.success(request, "Modalidad actualizada.")
        return redirect("titulacion:modalidades_configuradas_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Editar modalidad", "page_title": "Editar modalidad", "active_page": "modalidades_configuradas"})


@permiso_required("MODALIDAD_CONFIGURAR")
@require_POST
def modalidad_configurada_toggle(request, pk):
    """Nunca elimina físicamente: solo activa/desactiva. Expedientes existentes
    (proyectos ya usando esta modalidad) siguen consultables sin cambios."""
    modalidad = get_object_or_404(ModalidadConfigurada, pk=pk)
    modalidad.esta_activa = not modalidad.esta_activa
    modalidad.actualizado_por = request.user
    modalidad.save(update_fields=("esta_activa", "actualizado_por", "fecha_actualizacion"))
    registrar_evento(request, accion="alternar_modalidad_configurada", tabla="modalidades_configuradas", registro_id=modalidad.pk, descripcion=f"Modalidad marcada como {'activa' if modalidad.esta_activa else 'inactiva'}.")
    messages.success(request, "Estado de la modalidad actualizado.")
    return redirect("titulacion:modalidades_configuradas_list")


@permiso_required("MODALIDAD_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def etapa_producto_create(request, modalidad_pk):
    modalidad = get_object_or_404(ModalidadConfigurada, pk=modalidad_pk)
    formulario = EtapaProductoForm(request.POST or None, initial={"modalidad": modalidad})
    if request.method == "POST" and formulario.is_valid():
        etapa = formulario.save(commit=False)
        etapa.modalidad = modalidad
        etapa.full_clean()
        etapa.save()
        registrar_evento(request, accion="crear_etapa_producto", tabla="etapas_producto", registro_id=etapa.pk, descripcion=f"Se creó la etapa {etapa.nombre}.")
        messages.success(request, "Etapa creada.")
        return redirect("titulacion:modalidades_configuradas_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": f"Nueva etapa · {modalidad.nombre}", "page_title": "Nueva etapa", "active_page": "modalidades_configuradas"})


@permiso_required("MODALIDAD_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def etapa_producto_update(request, pk):
    etapa = get_object_or_404(EtapaProducto, pk=pk)
    formulario = EtapaProductoForm(request.POST or None, instance=etapa)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        registrar_evento(request, accion="editar_etapa_producto", tabla="etapas_producto", registro_id=etapa.pk, descripcion=f"Se editó la etapa {etapa.nombre}.")
        messages.success(request, "Etapa actualizada.")
        return redirect("titulacion:modalidades_configuradas_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Editar etapa", "page_title": "Editar etapa", "active_page": "modalidades_configuradas"})


@permiso_required("MODALIDAD_CONFIGURAR")
@require_POST
def etapa_producto_toggle(request, pk):
    etapa = get_object_or_404(EtapaProducto, pk=pk)
    etapa.esta_activa = not etapa.esta_activa
    etapa.save(update_fields=("esta_activa", "fecha_actualizacion"))
    messages.success(request, "Estado de la etapa actualizado.")
    return redirect("titulacion:modalidades_configuradas_list")


# ---------------------------------------------------------------------------
# Fase 7C — Autorización de novena tutoría (solo coordinación)
# ---------------------------------------------------------------------------


@permiso_required("NOVENA_TUTORIA_AUTORIZAR")
@require_http_methods(["GET", "POST"])
def novena_tutoria_autorizar(request, proyecto_pk):
    _exigir_rol(request, "coordinador")
    proyecto = get_object_or_404(ProyectoTitulacion, pk=proyecto_pk)
    if tiene_autorizacion_novena_tutoria(proyecto):
        messages.info(request, "Este proyecto ya tiene una novena tutoría autorizada.")
        return redirect("titulacion:proyecto_detail", pk=proyecto.pk)
    formulario = AutorizacionNovenaTutoriaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            autorizar_novena_tutoria(
                proyecto, formulario.cleaned_data["motivo"], request.user, request=request
            )
            messages.success(request, "Novena tutoría autorizada. Ya puede programarse.")
            return redirect("titulacion:proyecto_detail", pk=proyecto.pk)
        except (PermissionDenied, ValidationError) as error:
            _mensaje_validacion(request, error)
    return render(
        request,
        "titulacion/form.html",
        {
            "form": formulario,
            "titulo": f"Autorizar novena tutoría · {proyecto.tema}",
            "nota": (
                "El trigger SQL fase7_validar_novena_tutoria es la garantía final: "
                "sin esta autorización, la base de datos rechaza cualquier tutoría número 9."
            ),
            "page_title": "Autorizar novena tutoría",
            "active_page": "calendario_tutorias",
        },
    )


# ---------------------------------------------------------------------------
# Fase 7D — Examen complexivo y escala de calificación
# ---------------------------------------------------------------------------


@usuario_activo_required
def examenes_complexivos_list(request):
    consulta = ExamenComplexivo.objects.select_related("proyecto", "escala").filter(
        proyecto__in=proyectos_visibles(request.user)
    ).order_by("-fecha_creacion")
    return render(
        request,
        "titulacion/examenes_complexivos_list.html",
        {
            "examenes": consulta,
            "puede_gestionar": usuario_tiene_permiso(request.user, "EXAMEN_COMPLEXIVO_GESTIONAR"),
            "page_title": "Exámenes complexivos",
            "page_subtitle": "Convocatoria, tribunal y resultado por intento",
            "active_page": "examenes_complexivos",
        },
    )


@permiso_required("EXAMEN_COMPLEXIVO_GESTIONAR")
@require_http_methods(["GET", "POST"])
def examen_complexivo_create(request, proyecto_pk):
    _exigir_rol(request, "coordinador")
    proyecto = get_object_or_404(ProyectoTitulacion, pk=proyecto_pk)
    formulario = ExamenComplexivoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        examen = formulario.save(commit=False)
        examen.proyecto = proyecto
        examen.registrado_por = request.user
        examen.full_clean()
        examen.save()
        registrar_evento(request, accion="crear_examen_complexivo", tabla="examenes_complexivos", registro_id=examen.pk, descripcion="Se registró un intento de examen complexivo.")
        messages.success(request, "Examen complexivo registrado.")
        return redirect("titulacion:examenes_complexivos_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": f"Registrar examen · {proyecto.tema}", "page_title": "Registrar examen complexivo", "active_page": "examenes_complexivos"})


@permiso_required("EXAMEN_COMPLEXIVO_GESTIONAR")
@require_http_methods(["GET", "POST"])
def examen_complexivo_update(request, pk):
    _exigir_rol(request, "coordinador")
    examen = get_object_or_404(ExamenComplexivo, pk=pk)
    formulario = ExamenComplexivoForm(request.POST or None, instance=examen)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        registrar_evento(request, accion="editar_examen_complexivo", tabla="examenes_complexivos", registro_id=examen.pk, descripcion="Se actualizó el examen complexivo.")
        messages.success(request, "Examen complexivo actualizado.")
        return redirect("titulacion:examenes_complexivos_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Editar examen complexivo", "page_title": "Editar examen complexivo", "active_page": "examenes_complexivos"})


@permiso_required("ESCALA_CALIFICACION_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def escala_calificacion_create(request):
    formulario = EscalaCalificacionForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Escala de calificación creada.")
        return redirect("titulacion:examenes_complexivos_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Nueva escala de calificación", "nota": "Evita usar una calificación numérica sin una escala configurada por programa o modalidad.", "page_title": "Nueva escala", "active_page": "examenes_complexivos"})


@permiso_required("ESCALA_CALIFICACION_CONFIGURAR")
@require_http_methods(["GET", "POST"])
def escala_calificacion_update(request, pk):
    escala = get_object_or_404(EscalaCalificacion, pk=pk)
    formulario = EscalaCalificacionForm(request.POST or None, instance=escala)
    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Escala de calificación actualizada.")
        return redirect("titulacion:examenes_complexivos_list")
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Editar escala de calificación", "page_title": "Editar escala", "active_page": "examenes_complexivos"})
