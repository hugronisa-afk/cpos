from functools import wraps
from pathlib import PurePosixPath
from urllib.parse import urlparse

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.decorators import usuario_activo_required
from apps.titulacion.forms import EntregaEtapaForm, EvaluarEntregaEtapaForm
from apps.titulacion.services import (
    etapa_esta_bloqueada,
    etapas_de_modalidad,
    crear_entrega_etapa,
    evaluar_entrega_etapa,
    obtener_proyecto_visible,
    onboarding_completado,
    puede_evaluar_entrega_etapa,
    puede_subir_entrega_etapa,
    rol_usuario,
)
from apps.titulacion.models import (
    Articulo,
    AsistenciaTutoria,
    ArchivoProyecto,
    EntregaEtapa,
    EstadoArticulo,
    EstadoEtapaProducto,
    EstadoTutoria,
    EtapaProducto,
    Grabacion,
    ModalidadConfigurada,
    TipoGrabacion,
    Tutoria,
)
from apps.titulacion.storage import (
    ErrorAlmacenamiento,
    MAX_DOCUMENTO,
    MAX_GRABACION,
    eliminar_archivo,
    guardar_archivo,
    respuesta_descarga,
)

from .forms import (
    ArticuloSeccionForm,
    AsistenciaTutoriaForm,
    ChecklistCierreForm,
    CorreccionEvidenciaForm,
    EnvioRevistaForm,
    EvidenciaForm,
    GrabacionForm,
    ValidacionEvidenciaForm,
)
from .models import Evidencia, EvidenciaVersion, ValidacionEvidencia
from .services import (
    calcular_avance_articulo,
    crear_version_grabacion,
    es_coordinador,
    es_rol_consulta_general,
    obtener_articulo_proyecto,
    obtener_asistencias_tutoria,
    obtener_dashboard_seguimiento,
    obtener_evidencias_por_tutoria,
    obtener_evidencias_por_usuario,
    obtener_grabaciones_tutoria,
    obtener_historial_evidencia,
    obtener_estado_integridad_tutoria,
    obtener_nombre_rol,
    obtener_notificaciones_usuario,
    obtener_proyectos_del_usuario,
    obtener_reportes_seguimiento,
    obtener_siguiente_numero_version,
    obtener_tutorias_por_usuario,
    obtener_checklist_cierre,
    registrar_bitacora,
    registrar_o_corregir_asistencia,
    tutoria_ya_finalizo,
    usuario_puede_corregir_asistencia,
    usuario_puede_editar_articulo,
    usuario_puede_gestionar_grabacion,
    usuario_puede_registrar_asistencia,
    usuario_puede_subir_evidencia,
    usuario_puede_validar_evidencia,
)


def _render(request, template_names, context=None):
    return render(request, template_names, context or {})


def _denegar(mensaje):
    raise PermissionDenied(mensaje)


def _nombre_archivo(referencia, prefijo, registro_id):
    ruta = str(referencia or "").split(":", 1)[-1]
    extension = PurePosixPath(ruta).suffix or ".bin"
    return f"{prefijo}-{registro_id}{extension}"


def usuario_activo_y_onboarding_completado(view_func):
    """Gate real (no solo UI) del recorrido de seguimiento del maestrante.

    Combina `usuario_activo_required` con el requisito de Fase 7A: mientras
    `OnboardingMaestrante` no esté en estado 'completado', el maestrante es
    redirigido al onboarding en lugar de acceder al dashboard, tutorías o
    evidencias. Tutor/coordinador/supervisor no se ven afectados.
    """

    @usuario_activo_required
    @wraps(view_func)
    def envoltura(request, *args, **kwargs):
        if not onboarding_completado(request.user):
            messages.warning(
                request,
                "Debe completar el onboarding de titulación antes de continuar.",
            )
            return redirect("titulacion:onboarding_gate")
        return view_func(request, *args, **kwargs)

    return envoltura


@usuario_activo_y_onboarding_completado
def dashboard_seguimiento(request):
    return _render(
        request,
        "seguimiento/dashboard.html",
        obtener_dashboard_seguimiento(request.user),
    )


@usuario_activo_y_onboarding_completado
def lista_tutorias(request):
    tutorias = list(obtener_tutorias_por_usuario(request.user))
    for tutoria in tutorias:
        tutoria.integridad_fase6 = obtener_estado_integridad_tutoria(tutoria)
        tutoria.esta_vencida = (
            tutoria.estado in {EstadoTutoria.PROGRAMADA, EstadoTutoria.REPROGRAMADA}
            and tutoria_ya_finalizo(tutoria)
        )
    return _render(
        request,
        "seguimiento/tutorias_list.html",
        {
            "tutorias": tutorias,
            "rol": obtener_nombre_rol(request.user),
        },
    )


@usuario_activo_y_onboarding_completado
def detalle_tutoria(request, tutoria_id):
    tutoria = get_object_or_404(
        obtener_tutorias_por_usuario(request.user),
        pk=tutoria_id,
    )
    estado_integridad = obtener_estado_integridad_tutoria(tutoria)
    asistencia = estado_integridad["asistencia"]
    puede_registrar = (
        asistencia is None
        and tutoria_ya_finalizo(tutoria)
        and usuario_puede_registrar_asistencia(request.user, tutoria)
    )
    puede_corregir = (
        asistencia is not None
        and usuario_puede_corregir_asistencia(request.user, tutoria)
    )
    puede_cancelar = (
        asistencia is None
        and usuario_puede_corregir_asistencia(request.user, tutoria)
        and tutoria.estado != EstadoTutoria.CANCELADA
    )
    tiene_grabacion = estado_integridad["tiene_grabacion"]
    puede_grabacion = (
        estado_integridad["realizada_valida"]
        and usuario_puede_gestionar_grabacion(
            request.user,
            tutoria,
            reemplazo=tiene_grabacion,
        )
    )
    return _render(
        request,
        "seguimiento/tutoria_detail.html",
        {
            "tutoria": tutoria,
            "asistencias": obtener_asistencias_tutoria(tutoria),
            "historial_asistencia": tutoria.historial_asistencia.select_related(
                "corregido_por"
            ).all(),
            "grabaciones": obtener_grabaciones_tutoria(tutoria),
            "evidencias": obtener_evidencias_por_tutoria(tutoria),
            "puede_registrar_asistencia": puede_registrar,
            "puede_corregir_asistencia": puede_corregir,
            "puede_cancelar_asistencia": puede_cancelar,
            "puede_registrar_grabacion": puede_grabacion,
            "reemplaza_grabacion": tiene_grabacion,
            "estado_integridad": estado_integridad,
            "puede_subir_evidencia": (
                usuario_puede_subir_evidencia(request.user, tutoria)
                and not Evidencia.objects.filter(tutoria=tutoria).exists()
            ),
            "puede_validar_evidencia": usuario_puede_validar_evidencia(request.user),
            "rol": obtener_nombre_rol(request.user),
        },
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def registrar_asistencia(request, tutoria_id):
    tutoria = get_object_or_404(
        obtener_tutorias_por_usuario(request.user),
        pk=tutoria_id,
    )
    asistencia = AsistenciaTutoria.objects.filter(tutoria=tutoria).first()
    es_correccion = asistencia is not None
    solo_cancelar = (
        asistencia is None
        and usuario_puede_corregir_asistencia(request.user, tutoria)
    )
    if es_correccion:
        if not usuario_puede_corregir_asistencia(request.user, tutoria):
            _denegar("Solo coordinación puede corregir una asistencia registrada.")
    elif not (
        usuario_puede_registrar_asistencia(request.user, tutoria)
        or solo_cancelar
    ):
        _denegar("Solo el tutor asignado puede registrar la asistencia.")
    inicial = {
        "estado_tutoria": (
            tutoria.estado
            if asistencia
            else (
                EstadoTutoria.CANCELADA
                if solo_cancelar
                else EstadoTutoria.REALIZADA
            )
        ),
        "asistio_tutor": asistencia.asistio_tutor if asistencia else False,
        "asistio_maestrante": (
            asistencia.asistio_maestrante if asistencia else False
        ),
        "observaciones": asistencia.observaciones if asistencia else "",
    }
    formulario = AsistenciaTutoriaForm(
        request.POST or None,
        initial=inicial,
        es_correccion=es_correccion,
        permite_cancelar=es_correccion or solo_cancelar,
        solo_cancelar=solo_cancelar,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            registrar_o_corregir_asistencia(
                tutoria,
                actor=request.user,
                asistio_tutor=formulario.cleaned_data["asistio_tutor"],
                asistio_maestrante=formulario.cleaned_data["asistio_maestrante"],
                estado_tutoria=formulario.cleaned_data["estado_tutoria"],
                observaciones=formulario.cleaned_data["observaciones"],
                motivo_correccion=formulario.cleaned_data.get(
                    "motivo_correccion"
                ),
                request=request,
            )
        except (ValidationError, PermissionDenied) as error:
            formulario.add_error(None, error)
        else:
            messages.success(
                request,
                (
                    "Asistencia corregida con historial."
                    if es_correccion
                    else (
                        "Tutoría cancelada con motivo registrado."
                        if solo_cancelar
                        else "Asistencia y estado registrados."
                    )
                ),
            )
            return redirect("seguimiento:detalle_tutoria", tutoria_id=tutoria.pk)
    return _render(
        request,
        "seguimiento/tutoria_form.html",
        {
            "form": formulario,
            "tutoria": tutoria,
            "modo": "asistencia",
            "es_correccion": es_correccion,
            "es_cancelacion": solo_cancelar,
        },
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def registrar_grabacion(request, tutoria_id):
    tutoria = get_object_or_404(
        obtener_tutorias_por_usuario(request.user),
        pk=tutoria_id,
    )
    estado_integridad = obtener_estado_integridad_tutoria(tutoria)
    grabacion_activa = estado_integridad["grabacion"]
    if not estado_integridad["realizada_valida"]:
        _denegar(
            "La grabación requiere una tutoría realizada con asistencia completa."
        )
    if not usuario_puede_gestionar_grabacion(
        request.user,
        tutoria,
        reemplazo=bool(grabacion_activa),
    ):
        _denegar("Solo el tutor asignado puede registrar o reemplazar la grabación.")

    formulario = GrabacionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        referencia = None
        try:
            tipo = formulario.cleaned_data["tipo_grabacion"]
            datos = None
            if tipo == TipoGrabacion.ARCHIVO:
                datos = guardar_archivo(
                    formulario.cleaned_data["archivo"],
                    categoria="grabaciones",
                    proyecto_id=tutoria.proyecto_id,
                    extensiones={"mp4", "webm", "mp3"},
                    limite_bytes=MAX_GRABACION,
                )
                referencia = datos["referencia"]
            grabacion = crear_version_grabacion(
                tutoria,
                actor=request.user,
                datos={
                    "tipo_grabacion": tipo,
                    "enlace_grabacion": formulario.cleaned_data.get(
                        "enlace_grabacion"
                    ),
                    "ruta_archivo": referencia,
                    "nombre_original": datos["nombre_original"] if datos else None,
                    "extension": datos["extension"] if datos else None,
                    "tamano_bytes": datos["tamano_bytes"] if datos else None,
                },
                request=request,
            )
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
        except (ValidationError, PermissionDenied) as error:
            if referencia:
                eliminar_archivo(referencia)
            formulario.add_error(None, error)
        except Exception:
            if referencia:
                eliminar_archivo(referencia)
            raise
        else:
            messages.success(
                request,
                "Grabación reemplazada y versión anterior conservada."
                if grabacion_activa
                else "Grabación registrada.",
            )
            return redirect("seguimiento:detalle_tutoria", tutoria_id=tutoria.pk)
    return _render(
        request,
        "seguimiento/tutoria_form.html",
        {
            "form": formulario,
            "tutoria": tutoria,
            "modo": "grabacion",
            "es_reemplazo": grabacion_activa is not None,
        },
    )


@usuario_activo_y_onboarding_completado
def grabacion_download(request, grabacion_id):
    grabacion = get_object_or_404(
        Grabacion.objects.select_related("tutoria__proyecto"),
        pk=grabacion_id,
        tutoria__proyecto__in=obtener_proyectos_del_usuario(request.user),
        tipo_grabacion=TipoGrabacion.ARCHIVO,
    )
    nombre = grabacion.nombre_original or _nombre_archivo(
        grabacion.ruta_archivo,
        "grabacion",
        grabacion.pk,
    )
    return respuesta_descarga(grabacion.ruta_archivo, nombre)


@usuario_activo_y_onboarding_completado
def grabacion_enlace(request, grabacion_id):
    grabacion = get_object_or_404(
        Grabacion.objects.select_related("tutoria__proyecto"),
        pk=grabacion_id,
        tutoria__proyecto__in=obtener_proyectos_del_usuario(request.user),
        tipo_grabacion=TipoGrabacion.ENLACE,
    )
    enlace = str(grabacion.enlace_grabacion or "")
    if urlparse(enlace).scheme != "https":
        _denegar("El enlace de grabación no es seguro.")
    return redirect(enlace)


@usuario_activo_y_onboarding_completado
def lista_evidencias(request):
    return _render(
        request,
        "seguimiento/evidencias_list.html",
        {
            "evidencias": obtener_evidencias_por_usuario(request.user),
            "rol": obtener_nombre_rol(request.user),
            "puede_subir_evidencia": usuario_puede_subir_evidencia(request.user),
            "puede_validar_evidencia": usuario_puede_validar_evidencia(
                request.user
            ),
        },
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def subir_evidencia(request, tutoria_id):
    if not usuario_puede_subir_evidencia(request.user):
        _denegar("Solo el maestrante puede subir evidencias.")
    tutoria = get_object_or_404(
        obtener_tutorias_por_usuario(request.user),
        pk=tutoria_id,
    )
    if not usuario_puede_subir_evidencia(request.user, tutoria):
        _denegar(
            "La evidencia requiere una tutoría propia, realizada y con asistencia completa."
        )
    if Evidencia.objects.filter(tutoria=tutoria).exists():
        messages.warning(
            request,
            "Esta tutoría ya tiene una evidencia. Use la corrección para crear nuevas versiones.",
        )
        evidencia = Evidencia.objects.filter(tutoria=tutoria).first()
        return redirect("seguimiento:detalle_evidencia", evidencia_id=evidencia.pk)

    formulario = EvidenciaForm(
        request.POST or None,
        request.FILES or None,
        tutoria=tutoria,
        proyecto=tutoria.proyecto,
    )
    if request.method == "POST" and formulario.is_valid():
        referencia = None
        try:
            datos = guardar_archivo(
                formulario.cleaned_data["archivo"],
                categoria="evidencias",
                proyecto_id=tutoria.proyecto_id,
                extensiones={"pdf", "doc", "docx"},
                limite_bytes=MAX_DOCUMENTO,
            )
            referencia = datos["referencia"]
            with transaction.atomic():
                tutoria_bloqueada = Tutoria.objects.select_for_update().get(
                    pk=tutoria.pk
                )
                if Evidencia.objects.filter(tutoria=tutoria_bloqueada).exists():
                    raise ValidationError(
                        "La tutoría ya recibió una evidencia en otra solicitud."
                    )
                evidencia = Evidencia.objects.create(
                    proyecto=tutoria_bloqueada.proyecto,
                    tutoria=tutoria_bloqueada,
                    subido_por=request.user,
                    tipo_avance=formulario.cleaned_data["tipo_avance"],
                    titulo=formulario.cleaned_data["titulo"],
                    descripcion=formulario.cleaned_data["descripcion"] or None,
                    archivo_url=referencia,
                    estado="en_revision",
                    version_actual=1,
                )
                EvidenciaVersion.objects.create(
                    evidencia=evidencia,
                    numero_version=1,
                    archivo_url=referencia,
                    comentario="Carga inicial de evidencia.",
                    subido_por=request.user,
                    estado="en_revision",
                )
                registrar_bitacora(
                    request.user,
                    accion="subir_evidencia",
                    descripcion=f"Se subió la evidencia de la tutoría {tutoria.pk}.",
                    tabla_afectada="evidencias",
                    registro_id=evidencia.pk,
                    request=request,
                )
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
        except ValidationError as error:
            if referencia:
                eliminar_archivo(referencia)
            formulario.add_error(None, error)
        except Exception:
            if referencia:
                eliminar_archivo(referencia)
            raise
        else:
            messages.success(request, "Evidencia subida y enviada a revisión.")
            return redirect(
                "seguimiento:detalle_evidencia",
                evidencia_id=evidencia.pk,
            )
    return _render(
        request,
        "seguimiento/evidencia_form.html",
        {"form": formulario, "tutoria": tutoria, "proyecto": tutoria.proyecto},
    )


@usuario_activo_y_onboarding_completado
def detalle_evidencia(request, evidencia_id):
    evidencia = get_object_or_404(
        obtener_evidencias_por_usuario(request.user),
        pk=evidencia_id,
    )
    historial = obtener_historial_evidencia(evidencia)
    return _render(
        request,
        "seguimiento/evidencia_detail.html",
        {
            "evidencia": evidencia,
            "versiones": historial["versiones"],
            "validaciones": historial["validaciones"],
            "puede_validar": (
                evidencia.estado in {"pendiente", "cargada", "en_revision"}
                and usuario_puede_validar_evidencia(request.user, evidencia)
            ),
            "puede_corregir": (
                evidencia.estado == "observada"
                and usuario_puede_subir_evidencia(request.user, evidencia.tutoria)
            ),
            "rol": obtener_nombre_rol(request.user),
        },
    )


@usuario_activo_y_onboarding_completado
def descargar_evidencia(request, evidencia_id):
    evidencia = get_object_or_404(
        obtener_evidencias_por_usuario(request.user),
        pk=evidencia_id,
    )
    return respuesta_descarga(
        evidencia.archivo_url,
        _nombre_archivo(evidencia.archivo_url, "evidencia", evidencia.pk),
    )


@usuario_activo_y_onboarding_completado
def descargar_version(request, version_id):
    version = get_object_or_404(
        EvidenciaVersion.objects.select_related("evidencia__proyecto"),
        pk=version_id,
        evidencia__proyecto__in=obtener_proyectos_del_usuario(request.user),
    )
    return respuesta_descarga(
        version.archivo_url,
        _nombre_archivo(version.archivo_url, "evidencia-version", version.pk),
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def validar_evidencia(request, evidencia_id):
    if not usuario_puede_validar_evidencia(request.user):
        _denegar("Solo el tutor asignado puede validar evidencias.")
    evidencia = get_object_or_404(
        obtener_evidencias_por_usuario(request.user),
        pk=evidencia_id,
    )
    if not usuario_puede_validar_evidencia(request.user, evidencia):
        _denegar("Solo el tutor asignado a esta tutoría puede decidir.")
    if evidencia.estado not in {"pendiente", "cargada", "en_revision"}:
        _denegar("Esta evidencia no se encuentra pendiente de revisión.")

    formulario = ValidacionEvidenciaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            evidencia = Evidencia.objects.select_for_update().get(pk=evidencia.pk)
            if evidencia.estado not in {"pendiente", "cargada", "en_revision"}:
                messages.warning(
                    request,
                    "La evidencia ya fue revisada en otra solicitud.",
                )
                return redirect(
                    "seguimiento:detalle_evidencia",
                    evidencia_id=evidencia.pk,
                )
            version = EvidenciaVersion.objects.select_for_update().get(
                evidencia=evidencia,
                numero_version=evidencia.version_actual,
            )
            if ValidacionEvidencia.objects.filter(
                evidencia_version=version
            ).exists():
                messages.warning(
                    request,
                    "La versión actual ya fue revisada en otra solicitud.",
                )
                return redirect(
                    "seguimiento:detalle_evidencia",
                    evidencia_id=evidencia.pk,
                )
            validacion = ValidacionEvidencia.objects.create(
                evidencia=evidencia,
                evidencia_version=version,
                validado_por=request.user,
                estado_resultado=formulario.cleaned_data["estado_resultado"],
                observaciones=formulario.cleaned_data["observaciones"] or None,
            )
            evidencia.estado = validacion.estado_resultado
            evidencia.fecha_actualizacion = timezone.now()
            evidencia.save(update_fields=("estado", "fecha_actualizacion"))
            version.estado = validacion.estado_resultado
            version.fecha_actualizacion = timezone.now()
            version.save(update_fields=("estado", "fecha_actualizacion"))
            registrar_bitacora(
                request.user,
                accion="validar_evidencia",
                descripcion=f"La evidencia {evidencia.pk} quedó {evidencia.estado}.",
                tabla_afectada="validaciones_evidencia",
                registro_id=validacion.pk,
                request=request,
            )
        messages.success(request, "Revisión de evidencia registrada.")
        return redirect(
            "seguimiento:detalle_evidencia",
            evidencia_id=evidencia.pk,
        )
    return _render(
        request,
        "seguimiento/evidencia_validar.html",
        {"form": formulario, "evidencia": evidencia},
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def corregir_evidencia(request, evidencia_id):
    if not usuario_puede_subir_evidencia(request.user):
        _denegar("Solo el maestrante puede corregir evidencias.")
    evidencia = get_object_or_404(
        obtener_evidencias_por_usuario(request.user),
        pk=evidencia_id,
        estado="observada",
    )
    if not usuario_puede_subir_evidencia(request.user, evidencia.tutoria):
        _denegar("Solo el maestrante propietario puede corregir esta evidencia.")
    formulario = CorreccionEvidenciaForm(
        request.POST or None,
        request.FILES or None,
        evidencia=evidencia,
    )
    if request.method == "POST" and formulario.is_valid():
        referencia = None
        try:
            datos = guardar_archivo(
                formulario.cleaned_data["archivo"],
                categoria="evidencias",
                proyecto_id=evidencia.proyecto_id,
                extensiones={"pdf", "doc", "docx"},
                limite_bytes=MAX_DOCUMENTO,
            )
            referencia = datos["referencia"]
            with transaction.atomic():
                evidencia = Evidencia.objects.select_for_update().get(pk=evidencia.pk)
                if evidencia.estado != "observada":
                    raise ValidationError(
                        "La evidencia ya cambió de estado y no admite esta corrección."
                    )
                numero = obtener_siguiente_numero_version(evidencia)
                version = EvidenciaVersion.objects.create(
                    evidencia=evidencia,
                    numero_version=numero,
                    archivo_url=referencia,
                    comentario=formulario.cleaned_data["comentario"],
                    subido_por=request.user,
                    estado="en_revision",
                )
                evidencia.archivo_url = referencia
                evidencia.version_actual = numero
                evidencia.estado = "en_revision"
                evidencia.fecha_actualizacion = timezone.now()
                evidencia.save(
                    update_fields=(
                        "archivo_url",
                        "version_actual",
                        "estado",
                        "fecha_actualizacion",
                    )
                )
                registrar_bitacora(
                    request.user,
                    accion="corregir_evidencia",
                    descripcion=f"Se creó la versión {numero} de la evidencia {evidencia.pk}.",
                    tabla_afectada="evidencia_versiones",
                    registro_id=version.pk,
                    request=request,
                )
        except ErrorAlmacenamiento as error:
            messages.error(request, str(error))
        except ValidationError as error:
            if referencia:
                eliminar_archivo(referencia)
            formulario.add_error(None, error)
        except Exception:
            if referencia:
                eliminar_archivo(referencia)
            raise
        else:
            messages.success(request, "Corrección enviada a revisión.")
            return redirect(
                "seguimiento:detalle_evidencia",
                evidencia_id=evidencia.pk,
            )
    return _render(
        request,
        "seguimiento/evidencia_form.html",
        {"form": formulario, "evidencia": evidencia},
    )


@usuario_activo_y_onboarding_completado
def historial_evidencia(request, evidencia_id):
    evidencia = get_object_or_404(
        obtener_evidencias_por_usuario(request.user),
        pk=evidencia_id,
    )
    historial = obtener_historial_evidencia(evidencia)
    return _render(
        request,
        "seguimiento/evidencia_historial.html",
        {"evidencia": evidencia, **historial},
    )


@usuario_activo_y_onboarding_completado
def articulo_seguimiento(request, proyecto_id):
    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        pk=proyecto_id,
        modalidad="articulo_cientifico",
    )
    articulo = obtener_articulo_proyecto(proyecto)
    return _render(
        request,
        "seguimiento/articulo.html",
        {
            "proyecto": proyecto,
            "articulo": articulo,
            "avance_articulo": calcular_avance_articulo(articulo),
            "puede_editar": usuario_puede_editar_articulo(request.user, proyecto),
        },
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def editar_seccion_articulo(request, proyecto_id, seccion):
    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        pk=proyecto_id,
    )
    if not usuario_puede_editar_articulo(request.user, proyecto):
        _denegar("Solo el maestrante propietario puede editar el artículo.")
    articulo = obtener_articulo_proyecto(proyecto)
    if articulo is None:
        articulo = Articulo.objects.create(proyecto=proyecto)
    formulario = ArticuloSeccionForm(
        request.POST or None,
        initial={"seccion": seccion, "contenido": getattr(articulo, seccion, "") or ""},
        articulo=articulo,
    )
    if request.method == "POST" and formulario.is_valid():
        seccion_form = formulario.cleaned_data["seccion"]
        setattr(articulo, seccion_form, formulario.cleaned_data["contenido"])
        avance = calcular_avance_articulo(articulo)
        articulo.porcentaje_avance = avance["porcentaje"]
        articulo.save(
            update_fields=(
                seccion_form,
                "porcentaje_avance",
                "fecha_actualizacion",
            )
        )
        registrar_bitacora(
            request.user,
            accion="editar_seccion_articulo",
            descripcion=f"Se actualizó la sección {seccion_form} del artículo {articulo.pk}.",
            tabla_afectada="articulos",
            registro_id=articulo.pk,
            request=request,
        )
        messages.success(request, "Sección actualizada.")
        return redirect("seguimiento:articulo", proyecto_id=proyecto.pk)
    return _render(
        request,
        "seguimiento/articulo_form.html",
        {
            "form": formulario,
            "proyecto": proyecto,
            "articulo": articulo,
            "seccion": seccion,
        },
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def registrar_envio_revista(request, proyecto_id):
    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        pk=proyecto_id,
    )
    if not usuario_puede_editar_articulo(request.user, proyecto):
        _denegar("Solo el maestrante propietario puede registrar el envío.")
    articulo = obtener_articulo_proyecto(proyecto)
    if not articulo:
        _denegar("El proyecto todavía no tiene un artículo.")
    if calcular_avance_articulo(articulo)["porcentaje"] != 100:
        _denegar("El artículo debe tener todas sus secciones completas antes del envío.")
    formulario = EnvioRevistaForm(request.POST or None, instance=articulo)
    if request.method == "POST" and formulario.is_valid():
        articulo = formulario.save(commit=False)
        articulo.estado = EstadoArticulo.ENVIADO
        articulo.save()
        registrar_bitacora(
            request.user,
            accion="registrar_envio_revista",
            descripcion=f"Se registró el envío del artículo {articulo.pk}.",
            tabla_afectada="articulos",
            registro_id=articulo.pk,
            request=request,
        )
        messages.success(request, "Envío a revista registrado.")
        return redirect("seguimiento:articulo", proyecto_id=proyecto.pk)
    return _render(
        request,
        "seguimiento/articulo_form.html",
        {"form": formulario, "proyecto": proyecto, "articulo": articulo},
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def checklist_cierre(request, proyecto_id):
    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        pk=proyecto_id,
    )
    checklist = obtener_checklist_cierre(proyecto)
    formulario = ChecklistCierreForm(
        request.POST or None,
        puede_cerrar=checklist["puede_cerrar"],
    )
    if request.method == "POST":
        if not es_coordinador(request.user):
            _denegar("Solo coordinación puede confirmar el checklist.")
        if formulario.is_valid():
            registrar_bitacora(
                request.user,
                accion="revisar_checklist_cierre",
                descripcion=f"Se revisó el checklist del proyecto {proyecto.pk}.",
                tabla_afectada="proyectos_titulacion",
                registro_id=proyecto.pk,
                request=request,
            )
            messages.success(request, "Checklist revisado.")
            return redirect("seguimiento:checklist_cierre", proyecto_id=proyecto.pk)
    return _render(
        request,
        "seguimiento/checklist_cierre.html",
        {
            "form": formulario,
            "proyecto": proyecto,
            "checklist": checklist,
            "puede_confirmar": es_coordinador(request.user),
        },
    )


@usuario_activo_y_onboarding_completado
def reportes_seguimiento(request):
    if not es_rol_consulta_general(request.user):
        _denegar("Solo coordinación o supervisión pueden consultar reportes.")
    contexto = obtener_reportes_seguimiento(request.user)
    contexto["rol"] = obtener_nombre_rol(request.user)
    return _render(request, "seguimiento/reportes.html", contexto)


@usuario_activo_y_onboarding_completado
def notificaciones_seguimiento(request):
    return _render(
        request,
        "seguimiento/notificaciones.html",
        {
            "notificaciones": obtener_notificaciones_usuario(request.user),
            "rol": obtener_nombre_rol(request.user),
        },
    )


# ---------------------------------------------------------------------------
# Fase 7D — Entregas por etapa del producto final
# ---------------------------------------------------------------------------


def _modalidad_configurada_del_proyecto(proyecto):
    return ModalidadConfigurada.objects.filter(
        tipo_modalidad=proyecto.modalidad, es_semilla_base=True
    ).first() or ModalidadConfigurada.objects.filter(
        tipo_modalidad=proyecto.modalidad, programa=proyecto.maestrante.programa
    ).first()


@usuario_activo_y_onboarding_completado
def lista_entregas_etapa(request, proyecto_id):
    proyecto = obtener_proyecto_visible(request.user, proyecto_id)
    modalidad_configurada = _modalidad_configurada_del_proyecto(proyecto)
    etapas = list(etapas_de_modalidad(modalidad_configurada)) if modalidad_configurada else []
    for etapa in etapas:
        etapa.bloqueada = etapa_esta_bloqueada(proyecto, etapa)
        etapa.ultima_entrega = (
            EntregaEtapa.objects.filter(proyecto=proyecto, etapa=etapa)
            .order_by("-numero_version")
            .first()
        )
    return _render(
        request,
        "seguimiento/entregas_etapa.html",
        {
            "proyecto": proyecto,
            "modalidad_configurada": modalidad_configurada,
            "etapas": etapas,
            "puede_subir": puede_subir_entrega_etapa(request.user, proyecto),
            "puede_evaluar": puede_evaluar_entrega_etapa(request.user),
            "rol": obtener_nombre_rol(request.user),
        },
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def subir_entrega_etapa(request, proyecto_id, etapa_id):
    proyecto = obtener_proyecto_visible(request.user, proyecto_id)
    etapa = get_object_or_404(EtapaProducto, pk=etapa_id)
    if not puede_subir_entrega_etapa(request.user, proyecto):
        _denegar("Solo el maestrante propietario puede subir esta entrega.")
    if etapa_esta_bloqueada(proyecto, etapa):
        _denegar(
            "Esta etapa está bloqueada hasta que las etapas obligatorias previas sean aprobadas."
        )
    formulario = EntregaEtapaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        archivo_registro = None
        subido = formulario.cleaned_data.get("archivo")
        if subido:
            try:
                datos = guardar_archivo(
                    subido,
                    categoria="entregas-etapa",
                    proyecto_id=proyecto.pk,
                    extensiones={"doc", "docx", "pdf"},
                    limite_bytes=MAX_DOCUMENTO,
                )
                archivo_registro = ArchivoProyecto.objects.create(
                    proyecto=proyecto,
                    tipo_archivo="anexo",
                    nombre_original=datos["nombre_original"],
                    ruta_archivo=datos["referencia"],
                    extension=datos["extension"],
                    tamano_bytes=datos["tamano_bytes"],
                    subido_por=request.user,
                )
            except ErrorAlmacenamiento as error:
                messages.error(request, str(error))
                archivo_registro = None
        try:
            crear_entrega_etapa(
                proyecto,
                etapa,
                request.user,
                archivo=archivo_registro,
                comentario=formulario.cleaned_data.get("comentario"),
                request=request,
            )
            messages.success(request, f"Entrega registrada para la etapa {etapa.nombre}.")
            return redirect("seguimiento:entregas_etapa", proyecto_id=proyecto.pk)
        except (PermissionDenied, ValidationError) as error:
            for mensaje in getattr(error, "messages", [str(error)]):
                messages.error(request, mensaje)
    return _render(
        request,
        "seguimiento/entrega_etapa_form.html",
        {"form": formulario, "proyecto": proyecto, "etapa": etapa},
    )


@usuario_activo_y_onboarding_completado
@require_http_methods(["GET", "POST"])
def evaluar_entrega_etapa_view(request, entrega_id):
    entrega = get_object_or_404(
        EntregaEtapa.objects.select_related("proyecto", "etapa"), pk=entrega_id
    )
    if not puede_evaluar_entrega_etapa(request.user):
        _denegar("Solo coordinación puede evaluar entregas de etapa.")
    formulario = EvaluarEntregaEtapaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            evaluar_entrega_etapa(
                entrega,
                request.user,
                formulario.cleaned_data["estado"],
                evaluacion=formulario.cleaned_data.get("evaluacion"),
                observaciones=formulario.cleaned_data.get("observaciones"),
                request=request,
            )
            messages.success(request, "Entrega evaluada.")
            return redirect("seguimiento:entregas_etapa", proyecto_id=entrega.proyecto_id)
        except (PermissionDenied, ValidationError) as error:
            for mensaje in getattr(error, "messages", [str(error)]):
                messages.error(request, mensaje)
    return _render(
        request,
        "seguimiento/entrega_etapa_evaluar.html",
        {"form": formulario, "entrega": entrega},
    )
