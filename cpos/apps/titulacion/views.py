from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from urllib.parse import urlparse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import permiso_required, usuario_activo_required
from apps.accounts.services import usuario_tiene_permiso

from .forms import (
    ArchivoProyectoForm,
    ArticuloForm,
    AsignacionTutorForm,
    GrabacionForm,
    ProyectoForm,
    RegistroTutoriaForm,
    ReprogramacionTutoriaForm,
    ResolucionProyectoForm,
    RevisionArchivoForm,
    RevisionArticuloForm,
    RevisionProyectoForm,
    SolicitudCambioTemaForm,
    TutorForm,
    TutoriaForm,
)
from .models import (
    Aprobacion,
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    EstadoAsignacion,
    EstadoProyecto,
    EstadoReprogramacion,
    EstadoTutor,
    Grabacion,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    Tutor,
    Tutoria,
)
from .services import (
    asignar_tutor,
    enviar_proyecto_revision,
    obtener_proyecto_visible,
    puede_aprobar_proyecto,
    puede_crear_proyecto,
    puede_editar_articulo,
    puede_editar_proyecto,
    puede_gestionar_programacion,
    puede_registrar_sesion,
    puede_revisar_articulo,
    puede_revisar_archivo,
    puede_revisar_cambio_tema,
    puede_revisar_proyecto,
    puede_solicitar_cambio_tema,
    proyectos_visibles,
    registrar_evento,
    registrar_solicitud_aprobacion,
    resolver_cambio_tema,
    resolver_revision_archivo,
    resolver_reprogramacion,
    resolver_revision_proyecto,
    resumen_evidencias,
    rol_usuario,
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
    return Tutor.objects.select_related("usuario", "usuario__rol")


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
    asignacion = proyecto_obj.asignaciones_tutor.select_related("tutor__usuario").filter(estado=EstadoAsignacion.ACTIVO).first()
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
            "tutorias": proyecto_obj.tutorias.select_related("tutor__usuario").prefetch_related("grabaciones", "reprogramaciones").all(),
            "archivos": archivos,
            "articulos": proyecto_obj.articulos.filter(esta_activo=True),
            "cambios_tema": proyecto_obj.solicitudes_cambio_tema.select_related("solicitado_por").all(),
            "puede_editar": puede_editar_proyecto(request.user, proyecto_obj),
            "puede_revisar": proyecto_obj.estado == EstadoProyecto.EN_REVISION and puede_revisar_proyecto(request.user, proyecto_obj),
            "puede_aprobar": proyecto_obj.estado == EstadoProyecto.EN_REVISION and puede_aprobar_proyecto(request.user, proyecto_obj),
            "puede_asignar": proyecto_obj.estado == EstadoProyecto.APROBADO and rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "ASIGNACION_TUTOR_CREAR"),
            "puede_registrar_resolucion": proyecto_obj.estado == EstadoProyecto.APROBADO and rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "PROYECTO_APROBAR"),
            "puede_programar": puede_gestionar_programacion(request.user, proyecto_obj),
            "puede_subir_archivo": rol_usuario(request.user) == "maestrante" and proyecto_obj.maestrante.usuario_id == request.user.pk and usuario_tiene_permiso(request.user, "ARCHIVO_SUBIR"),
            "puede_cambio_tema": puede_solicitar_cambio_tema(request.user, proyecto_obj),
            "puede_revisar_cambio_tema": puede_revisar_cambio_tema(request.user, proyecto_obj),
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
    formulario = ProyectoForm(request.POST or None)
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
    formulario = ProyectoForm(request.POST or None, instance=proyecto_obj)
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
        enviar_proyecto_revision(proyecto_obj, request.user, request)
        messages.success(request, "Proyecto enviado a revisión.")
    except (PermissionDenied, ValidationError) as error:
        _mensaje_validacion(request, error)
    return redirect("titulacion:proyecto_detail", pk=pk)


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def proyecto_revisar(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not (puede_revisar_proyecto(request.user, proyecto_obj) or puede_aprobar_proyecto(request.user, proyecto_obj)):
        raise PermissionDenied("No puede revisar este proyecto.")
    formulario = RevisionProyectoForm(
        request.POST or None,
        puede_aprobar=puede_aprobar_proyecto(request.user, proyecto_obj),
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            resolver_revision_proyecto(proyecto_obj, request.user, formulario.cleaned_data["estado"], formulario.cleaned_data["observaciones"], request)
            messages.success(request, "Revisión registrada.")
            return redirect("titulacion:proyecto_detail", pk=pk)
        except (PermissionDenied, ValidationError) as error:
            _mensaje_validacion(request, error)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Revisar proyecto", "page_title": "Revisar proyecto", "active_page": "proyecto"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def proyecto_resolucion(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not (
        rol_usuario(request.user) == "coordinador"
        and proyecto_obj.estado == EstadoProyecto.APROBADO
        and usuario_tiene_permiso(request.user, "PROYECTO_APROBAR")
    ):
        raise PermissionDenied("Solo coordinación puede registrar la resolución.")
    formulario = ResolucionProyectoForm(
        request.POST or None,
        request.FILES or None,
        instance=proyecto_obj,
    )
    if request.method == "POST" and formulario.is_valid():
        referencia_nueva = None
        referencia_anterior = proyecto_obj.documento_resolucion_url
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
                registrar_evento(request, accion="registrar_resolucion", tabla="proyectos_titulacion", registro_id=pk, descripcion="Se registró la resolución del proyecto.")
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
            return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Registrar resolución", "page_title": "Resolución", "active_page": "proyecto"})
        except Exception:
            if referencia_nueva:
                eliminar_archivo(referencia_nueva)
            raise
        if referencia_nueva and referencia_anterior:
            eliminar_archivo(referencia_anterior)
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
    formulario = AsignacionTutorForm(request.POST or None)
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
def archivo_create(request, pk):
    proyecto_obj = obtener_proyecto_visible(request.user, pk)
    if not (rol_usuario(request.user) == "maestrante" and proyecto_obj.maestrante.usuario_id == request.user.pk and usuario_tiene_permiso(request.user, "ARCHIVO_SUBIR")):
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
    formulario = TutoriaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        tutoria = formulario.save(commit=False)
        tutoria.proyecto = proyecto_obj
        tutoria.tutor = asignacion.tutor
        tutoria.programada_por = request.user
        tutoria.save()
        registrar_evento(request, accion="programar_tutoria", tabla="tutorias", registro_id=tutoria.pk, descripcion=f"Se programó la tutoría {tutoria.numero_tutoria}.")
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
    formulario = ReprogramacionTutoriaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        reprogramacion = formulario.save(commit=False)
        reprogramacion.tutoria = tutoria
        reprogramacion.fecha_anterior = tutoria.fecha
        reprogramacion.hora_inicio_anterior = tutoria.hora_inicio
        reprogramacion.hora_fin_anterior = tutoria.hora_fin
        reprogramacion.solicitado_por = request.user
        reprogramacion.save()
        registrar_solicitud_aprobacion(
            proyecto=tutoria.proyecto,
            tipo="reprogramacion",
            tabla="reprogramaciones_tutoria",
            registro_id=reprogramacion.pk,
        )
        registrar_evento(request, accion="solicitar_reprogramacion", tabla="reprogramaciones_tutoria", registro_id=reprogramacion.pk, descripcion="Se solicitó reprogramar una tutoría.")
        messages.success(request, "Solicitud de reprogramación registrada.")
        return redirect("titulacion:proyecto_detail", pk=tutoria.proyecto_id)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Solicitar reprogramación", "page_title": "Reprogramar tutoría", "active_page": "proyecto"})


@usuario_activo_required
@require_POST
def reprogramacion_resolver(request, pk):
    reprogramacion = get_object_or_404(ReprogramacionTutoria.objects.select_related("tutoria__proyecto"), pk=pk, tutoria__proyecto__in=proyectos_visibles(request.user))
    aprobar = request.POST.get("decision") == "aprobar"
    try:
        resolver_reprogramacion(reprogramacion, request.user, aprobar, request)
        messages.success(request, "Reprogramación resuelta.")
    except (PermissionDenied, ValidationError) as error:
        _mensaje_validacion(request, error)
    return redirect("titulacion:proyecto_detail", pk=reprogramacion.tutoria.proyecto_id)


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
    proyectos = proyectos_visibles(request.user)
    articulos = Articulo.objects.select_related("proyecto", "proyecto__maestrante__usuario").filter(proyecto__in=proyectos, esta_activo=True)
    return render(request, "titulacion/articulo.html", {"articulos": articulos, "proyectos": proyectos, "rol_actual": rol_usuario(request.user), "page_title": "Artículos", "page_subtitle": "Artículos visibles para su rol", "active_page": "articulo"})


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def articulo_edit(request, proyecto_pk):
    proyecto_obj = obtener_proyecto_visible(request.user, proyecto_pk)
    articulo_obj = proyecto_obj.articulos.filter(esta_activo=True).first()
    if not puede_editar_articulo(request.user, proyecto_obj):
        raise PermissionDenied("No puede editar el artículo de este proyecto.")
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
        solicitud = formulario.save(commit=False)
        solicitud.proyecto = proyecto_obj
        solicitud.tema_actual = proyecto_obj.tema
        solicitud.solicitado_por = request.user
        solicitud.save()
        registrar_solicitud_aprobacion(
            proyecto=proyecto_obj,
            tipo="cambio_tema",
            tabla="solicitudes_cambio_tema",
            registro_id=solicitud.pk,
        )
        registrar_evento(request, accion="solicitar_cambio_tema", tabla="solicitudes_cambio_tema", registro_id=solicitud.pk, descripcion="Se solicitó un cambio de tema.")
        messages.success(request, "Solicitud de cambio de tema registrada.")
        return redirect("titulacion:proyecto_detail", pk=proyecto_pk)
    return render(request, "titulacion/form.html", {"form": formulario, "titulo": "Solicitar cambio de tema", "page_title": "Cambio de tema", "active_page": "proyecto"})


@usuario_activo_required
@require_POST
def cambio_tema_resolver(request, pk):
    solicitud = get_object_or_404(SolicitudCambioTema.objects.select_related("proyecto"), pk=pk, proyecto__in=proyectos_visibles(request.user))
    if not puede_revisar_cambio_tema(request.user, solicitud.proyecto):
        raise PermissionDenied("No puede resolver esta solicitud.")
    try:
        resolver_cambio_tema(solicitud, request.user, request.POST.get("decision") == "aprobar", request)
        messages.success(request, "Solicitud de cambio de tema resuelta.")
    except (PermissionDenied, ValidationError) as error:
        _mensaje_validacion(request, error)
    return redirect("titulacion:proyecto_detail", pk=solicitud.proyecto_id)


@usuario_activo_required
def aprobaciones(request):
    proyectos = proyectos_visibles(request.user)
    consulta = Aprobacion.objects.select_related("proyecto", "proyecto__maestrante__usuario", "aprobado_por").filter(proyecto__in=proyectos)
    return render(request, "titulacion/aprobaciones.html", {"aprobaciones": consulta, "pendientes": consulta.filter(estado="pendiente").count(), "aprobadas": consulta.filter(estado="aprobado").count(), "rechazadas": consulta.filter(estado="rechazado").count(), "rol_actual": rol_usuario(request.user), "page_title": "Aprobaciones", "page_subtitle": "Historial real de decisiones", "active_page": "aprobaciones"})


@usuario_activo_required
def requerimientos(request):
    return render(request, "titulacion/requerimientos.html", {"page_title": "Requerimientos", "page_subtitle": "Requerimientos del módulo", "active_page": "requerimientos"})


@permiso_required("TUTOR_VER")
def tutores_list(request):
    _exigir_rol(request, "coordinador", "supervisor")
    consulta = _consulta_tutores()
    busqueda = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    if busqueda:
        consulta = consulta.filter(Q(usuario__nombres__icontains=busqueda) | Q(usuario__apellidos__icontains=busqueda) | Q(usuario__correo__icontains=busqueda) | Q(especialidad__icontains=busqueda))
    if estado in {valor for valor, _ in EstadoTutor.choices}:
        consulta = consulta.filter(estado=estado)
    else:
        estado = ""
    return render(request, "titulacion/tutores_list.html", {"pagina": Paginator(consulta, 20).get_page(request.GET.get("page")), "busqueda": busqueda, "estado_seleccionado": estado, "estados": EstadoTutor.choices, "puede_crear": rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "TUTOR_CREAR"), "puede_editar": rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "TUTOR_EDITAR"), "page_title": "Tutores", "page_subtitle": "Perfiles académicos de tutores", "active_page": "tutores"})


@permiso_required("TUTOR_CREAR")
@require_http_methods(["GET", "POST"])
def tutor_create(request):
    _exigir_rol(request, "coordinador")
    formulario = TutorForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            tutor = formulario.save()
            registrar_evento(request, accion="crear_tutor", tabla="tutores", registro_id=tutor.pk, descripcion="Se registró el perfil académico del tutor.")
        messages.success(request, "Tutor registrado.")
        return redirect("titulacion:tutor_detail", pk=tutor.pk)
    return render(request, "titulacion/tutor_form.html", {"form": formulario, "hay_usuarios_disponibles": formulario.fields["usuario"].queryset.exists(), "modo": "crear", "page_title": "Registrar tutor", "page_subtitle": "Vincular cuenta institucional", "active_page": "tutores"})


@permiso_required("TUTOR_VER")
def tutor_detail(request, pk):
    _exigir_rol(request, "coordinador", "supervisor")
    tutor = get_object_or_404(_consulta_tutores(), pk=pk)
    return render(request, "titulacion/tutor_detail.html", {"tutor": tutor, "puede_editar": rol_usuario(request.user) == "coordinador" and usuario_tiene_permiso(request.user, "TUTOR_EDITAR"), "page_title": "Detalle de tutor", "page_subtitle": "Información institucional y académica", "active_page": "tutores"})


@permiso_required("TUTOR_EDITAR")
@require_http_methods(["GET", "POST"])
def tutor_update(request, pk):
    _exigir_rol(request, "coordinador")
    tutor = get_object_or_404(_consulta_tutores(), pk=pk)
    formulario = TutorForm(request.POST or None, instance=tutor)
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
    tutor = get_object_or_404(_consulta_tutores(), pk=pk)
    reactivar = tutor.estado == EstadoTutor.INACTIVO
    tutor.estado = EstadoTutor.DISPONIBLE if reactivar else EstadoTutor.INACTIVO
    tutor.save(update_fields=("estado", "fecha_actualizacion"))
    registrar_evento(request, accion="reactivar_tutor" if reactivar else "desactivar_tutor", tabla="tutores", registro_id=tutor.pk, descripcion="Se cambió el estado del perfil del tutor.")
    messages.success(request, "Estado del tutor actualizado.")
    return redirect("titulacion:tutor_detail", pk=tutor.pk)
