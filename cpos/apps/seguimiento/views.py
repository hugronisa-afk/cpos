from django.contrib import messages
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AsistenciaTutoriaForm,
    GrabacionForm,
    EvidenciaForm,
    ValidacionEvidenciaForm,
    CorreccionEvidenciaForm,
    ArticuloSeccionForm,
    EnvioRevistaForm,
    ChecklistCierreForm,
)

from .models import (
    Usuario,
    Tutor,
    ProyectoTitulacion,
    Tutoria,
    AsistenciaTutoria,
    Grabacion,
    Evidencia,
    EvidenciaVersion,
    ValidacionEvidencia,
    Articulo,
    Notificacion,
)

from .services import (
    obtener_usuario_sistema,
    obtener_nombre_rol,
    es_maestrante,
    es_tutor,
    es_coordinador,
    es_supervisor,
    es_rol_consulta_general,
    usuario_puede_ver_proyecto,
    usuario_puede_subir_evidencia,
    usuario_puede_validar_evidencia,
    obtener_proyectos_del_usuario,
    obtener_proyecto_del_usuario,
    obtener_tutorias_por_usuario,
    obtener_evidencias_por_usuario,
    obtener_evidencias_por_tutoria,
    obtener_asistencias_tutoria,
    obtener_grabaciones_tutoria,
    obtener_historial_evidencia,
    obtener_siguiente_numero_version,
    obtener_articulo_proyecto,
    calcular_avance_articulo,
    obtener_checklist_cierre,
    obtener_dashboard_seguimiento,
    obtener_reportes_seguimiento,
    obtener_notificaciones_usuario,
    registrar_bitacora,
)


# ============================================================
# HELPERS INTERNOS DE VISTAS
# ============================================================

def _render(request, template_names, context=None):
    """
    Permite usar varios nombres de template.

    Esto ayuda porque tu proyecto puede tener:
    - seguimiento/tutorias.html
    o más adelante:
    - seguimiento/tutorias_list.html

    Django usará el primero que exista.
    """
    return render(request, template_names, context or {})


def _get_tutor_usuario(usuario_sistema):
    """
    Obtiene el Tutor asociado al usuario actual.
    """
    if not usuario_sistema:
        return None

    return Tutor.objects.filter(usuario=usuario_sistema).first()


def _forbidden(request, mensaje="No tienes permisos para realizar esta acción."):
    messages.error(request, mensaje)
    return HttpResponseForbidden(mensaje)


# ============================================================
# DASHBOARD
# Ruta esperada:
# /seguimiento/
# ============================================================

@login_required(login_url="accounts:login")
def dashboard_seguimiento(request):
    """
    Dashboard principal del módulo seguimiento.
    Muestra avance de tutorías, evidencias, artículo y alertas.
    """

    context = obtener_dashboard_seguimiento(request.user)

    return _render(
        request,
        [
            "seguimiento/dashboard.html",
        ],
        context,
    )


# ============================================================
# TUTORÍAS
# Rutas esperadas:
# /seguimiento/tutorias/
# /seguimiento/tutorias/<id>/
# ============================================================

@login_required(login_url="accounts:login")
def lista_tutorias(request):
    """
    Lista las tutorías visibles según el rol:
    - Maestrante: sus tutorías.
    - Tutor: tutorías asignadas.
    - Coordinador/Supervisor: todas.
    """

    tutorias = obtener_tutorias_por_usuario(request.user)

    context = {
        "tutorias": tutorias,
        "rol": obtener_nombre_rol(request.user),
    }

    return _render(
        request,
        [
            "seguimiento/tutorias_list.html",
            "seguimiento/tutorias.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def detalle_tutoria(request, tutoria_id):
    """
    Muestra el detalle de una tutoría:
    asistencia, grabación y evidencias asociadas.
    """

    tutorias_permitidas = obtener_tutorias_por_usuario(request.user)

    tutoria = get_object_or_404(
        tutorias_permitidas,
        id=tutoria_id,
    )

    asistencias = obtener_asistencias_tutoria(tutoria)
    grabaciones = obtener_grabaciones_tutoria(tutoria)
    evidencias = obtener_evidencias_por_tutoria(tutoria)

    context = {
        "tutoria": tutoria,
        "asistencias": asistencias,
        "grabaciones": grabaciones,
        "evidencias": evidencias,
        "puede_subir_evidencia": usuario_puede_subir_evidencia(request.user),
        "puede_validar_evidencia": usuario_puede_validar_evidencia(request.user),
        "rol": obtener_nombre_rol(request.user),
    }

    return _render(
        request,
        [
            "seguimiento/tutoria_detail.html",
            "seguimiento/tutoria.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def registrar_asistencia(request, tutoria_id):
    """
    Registra asistencia del tutor y del maestrante.
    También actualiza el estado de la tutoría.
    """

    tutorias_permitidas = obtener_tutorias_por_usuario(request.user)

    tutoria = get_object_or_404(
        tutorias_permitidas,
        id=tutoria_id,
    )

    usuario_sistema = obtener_usuario_sistema(request.user)

    if not usuario_sistema:
        return _forbidden(request, "No se pudo identificar tu usuario del sistema.")

    if request.method == "POST":
        form = AsistenciaTutoriaForm(request.POST)

        if form.is_valid():
            asistio_tutor = form.cleaned_data["asistio_tutor"]
            asistio_maestrante = form.cleaned_data["asistio_maestrante"]
            estado_tutoria = form.cleaned_data["estado_tutoria"]
            observaciones = form.cleaned_data["observaciones"]

            # Actualizar estado de tutoría.
            tutoria.estado = estado_tutoria
            tutoria.observaciones = observaciones
            tutoria.actualizado_en = timezone.now()
            tutoria.save()

            # Usuario tutor.
            tutor_usuario = None
            if tutoria.tutor and tutoria.tutor.usuario:
                tutor_usuario = tutoria.tutor.usuario

            # Usuario maestrante.
            maestrante_usuario = None
            if tutoria.proyecto and tutoria.proyecto.maestrante:
                maestrante_usuario = tutoria.proyecto.maestrante.usuario

            if tutor_usuario:
                AsistenciaTutoria.objects.update_or_create(
                    tutoria=tutoria,
                    usuario=tutor_usuario,
                    tipo_participante="tutor",
                    defaults={
                        "asistio": asistio_tutor,
                        "observaciones": observaciones,
                        "registrado_por": usuario_sistema,
                        "fecha_registro": timezone.now(),
                    },
                )

            if maestrante_usuario:
                AsistenciaTutoria.objects.update_or_create(
                    tutoria=tutoria,
                    usuario=maestrante_usuario,
                    tipo_participante="maestrante",
                    defaults={
                        "asistio": asistio_maestrante,
                        "observaciones": observaciones,
                        "registrado_por": usuario_sistema,
                        "fecha_registro": timezone.now(),
                    },
                )

            registrar_bitacora(
                request.user,
                accion="Registrar asistencia",
                descripcion=f"Se registró asistencia de la tutoría {tutoria.id}.",
                tabla_afectada="tutorias",
                registro_id=tutoria.id,
                request=request,
            )

            messages.success(request, "Asistencia registrada correctamente.")
            return redirect("seguimiento:detalle_tutoria", tutoria_id=tutoria.id)

    else:
        form = AsistenciaTutoriaForm(initial={
            "estado_tutoria": tutoria.estado or "realizada",
        })

    context = {
        "form": form,
        "tutoria": tutoria,
    }

    return _render(
        request,
        [
            "seguimiento/asistencia_form.html",
            "seguimiento/tutoria_form.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def registrar_grabacion(request, tutoria_id):
    """
    Registra enlace o archivo de grabación para una tutoría.
    """

    tutorias_permitidas = obtener_tutorias_por_usuario(request.user)

    tutoria = get_object_or_404(
        tutorias_permitidas,
        id=tutoria_id,
    )

    usuario_sistema = obtener_usuario_sistema(request.user)

    if not usuario_sistema:
        return _forbidden(request, "No se pudo identificar tu usuario del sistema.")

    if request.method == "POST":
        form = GrabacionForm(request.POST, request.FILES)

        if form.is_valid():
            grabacion = form.save(commit=False)
            grabacion.tutoria = tutoria
            grabacion.proyecto = tutoria.proyecto
            grabacion.registrado_por = usuario_sistema
            grabacion.fecha_registro = timezone.now()
            grabacion.save()

            registrar_bitacora(
                request.user,
                accion="Registrar grabación",
                descripcion=f"Se registró grabación para la tutoría {tutoria.id}.",
                tabla_afectada="grabaciones",
                registro_id=grabacion.id,
                request=request,
            )

            messages.success(request, "Grabación registrada correctamente.")
            return redirect("seguimiento:detalle_tutoria", tutoria_id=tutoria.id)

    else:
        form = GrabacionForm()

    context = {
        "form": form,
        "tutoria": tutoria,
    }

    return _render(
        request,
        [
            "seguimiento/grabacion_form.html",
            "seguimiento/tutoria_form.html",
        ],
        context,
    )


# ============================================================
# EVIDENCIAS
# Rutas esperadas:
# /seguimiento/evidencias/
# /seguimiento/tutorias/<id>/evidencia/
# /seguimiento/evidencias/<id>/
# /seguimiento/evidencias/<id>/validar/
# /seguimiento/evidencias/<id>/corregir/
# /seguimiento/evidencias/<id>/historial/
# ============================================================

@login_required(login_url="accounts:login")
def lista_evidencias(request):
    """
    Lista evidencias visibles para el usuario.
    """

    evidencias = obtener_evidencias_por_usuario(request.user)

    context = {
        "evidencias": evidencias,
        "rol": obtener_nombre_rol(request.user),
        "puede_subir_evidencia": usuario_puede_subir_evidencia(request.user),
        "puede_validar_evidencia": usuario_puede_validar_evidencia(request.user),
    }

    return _render(
        request,
        [
            "seguimiento/evidencias_list.html",
            "seguimiento/evidencia.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def subir_evidencia(request, tutoria_id):
    """
    Permite subir una evidencia asociada a una tutoría.
    Regla:
    La evidencia queda asociada a:
    - la tutoría
    - el proyecto de esa tutoría
    """

    if not usuario_puede_subir_evidencia(request.user):
        return _forbidden(request, "No tienes permisos para subir evidencias.")

    tutorias_permitidas = obtener_tutorias_por_usuario(request.user)

    tutoria = get_object_or_404(
        tutorias_permitidas,
        id=tutoria_id,
    )

    proyecto = tutoria.proyecto
    usuario_sistema = obtener_usuario_sistema(request.user)

    if not usuario_sistema:
        return _forbidden(request, "No se pudo identificar tu usuario del sistema.")

    if request.method == "POST":
        form = EvidenciaForm(
            request.POST,
            request.FILES,
            tutoria=tutoria,
            proyecto=proyecto,
        )

        if form.is_valid():
            evidencia = form.save(commit=False)
            evidencia.tutoria = tutoria
            evidencia.proyecto = proyecto
            evidencia.estado = "pendiente"
            evidencia.cargado_por = usuario_sistema
            evidencia.fecha_carga = timezone.now()
            evidencia.actualizado_en = timezone.now()
            evidencia.save()

            # Primera versión de la evidencia.
            EvidenciaVersion.objects.create(
                evidencia=evidencia,
                numero_version=1,
                archivo=evidencia.archivo,
                enlace=evidencia.enlace,
                descripcion_cambios="Carga inicial de evidencia.",
                creado_por=usuario_sistema,
                creado_en=timezone.now(),
            )

            registrar_bitacora(
                request.user,
                accion="Subir evidencia",
                descripcion=f"Se subió evidencia {evidencia.id} para la tutoría {tutoria.id}.",
                tabla_afectada="evidencias",
                registro_id=evidencia.id,
                request=request,
            )

            messages.success(request, "Evidencia subida correctamente.")
            return redirect("seguimiento:detalle_evidencia", evidencia_id=evidencia.id)

    else:
        form = EvidenciaForm(
            tutoria=tutoria,
            proyecto=proyecto,
        )

    context = {
        "form": form,
        "tutoria": tutoria,
        "proyecto": proyecto,
    }

    return _render(
        request,
        [
            "seguimiento/evidencia_form.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def detalle_evidencia(request, evidencia_id):
    """
    Muestra detalle de una evidencia, sus validaciones y versiones.
    """

    evidencias_permitidas = obtener_evidencias_por_usuario(request.user)

    evidencia = get_object_or_404(
        evidencias_permitidas,
        id=evidencia_id,
    )

    historial = obtener_historial_evidencia(evidencia)

    context = {
        "evidencia": evidencia,
        "versiones": historial["versiones"],
        "validaciones": historial["validaciones"],
        "puede_validar": usuario_puede_validar_evidencia(request.user),
        "puede_corregir": evidencia.estado == "observada" and usuario_puede_subir_evidencia(request.user),
        "rol": obtener_nombre_rol(request.user),
    }

    return _render(
        request,
        [
            "seguimiento/evidencia_detail.html",
            "seguimiento/evidencia.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def validar_evidencia(request, evidencia_id):
    """
    Permite al tutor validar, observar o rechazar una evidencia.
    """

    if not usuario_puede_validar_evidencia(request.user):
        return _forbidden(request, "No tienes permisos para validar evidencias.")

    evidencias_permitidas = obtener_evidencias_por_usuario(request.user)

    evidencia = get_object_or_404(
        evidencias_permitidas,
        id=evidencia_id,
    )

    usuario_sistema = obtener_usuario_sistema(request.user)
    tutor = _get_tutor_usuario(usuario_sistema)

    if request.method == "POST":
        form = ValidacionEvidenciaForm(request.POST)

        if form.is_valid():
            validacion = form.save(commit=False)
            validacion.evidencia = evidencia
            validacion.tutor = tutor
            validacion.validado_por = usuario_sistema
            validacion.fecha_validacion = timezone.now()
            validacion.save()

            evidencia.estado = validacion.estado
            evidencia.actualizado_en = timezone.now()
            evidencia.save()

            registrar_bitacora(
                request.user,
                accion="Validar evidencia",
                descripcion=f"La evidencia {evidencia.id} fue marcada como {validacion.estado}.",
                tabla_afectada="validaciones_evidencia",
                registro_id=validacion.id,
                request=request,
            )

            messages.success(request, "Revisión de evidencia registrada correctamente.")
            return redirect("seguimiento:detalle_evidencia", evidencia_id=evidencia.id)

    else:
        form = ValidacionEvidenciaForm()

    context = {
        "form": form,
        "evidencia": evidencia,
    }

    return _render(
        request,
        [
            "seguimiento/evidencia_validar.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def corregir_evidencia(request, evidencia_id):
    """
    Permite al maestrante subir una nueva versión de una evidencia observada.
    """

    if not usuario_puede_subir_evidencia(request.user):
        return _forbidden(request, "No tienes permisos para corregir evidencias.")

    evidencias_permitidas = obtener_evidencias_por_usuario(request.user)

    evidencia = get_object_or_404(
        evidencias_permitidas,
        id=evidencia_id,
    )

    usuario_sistema = obtener_usuario_sistema(request.user)

    if evidencia.estado != "observada":
        messages.warning(request, "Solo puedes corregir evidencias que estén observadas.")
        return redirect("seguimiento:detalle_evidencia", evidencia_id=evidencia.id)

    if request.method == "POST":
        form = CorreccionEvidenciaForm(
            request.POST,
            request.FILES,
            evidencia=evidencia,
        )

        if form.is_valid():
            version = form.save(commit=False)
            version.evidencia = evidencia
            version.numero_version = obtener_siguiente_numero_version(evidencia)
            version.creado_por = usuario_sistema
            version.creado_en = timezone.now()
            version.save()

            # Actualizamos la evidencia principal a la nueva versión.
            if version.archivo:
                evidencia.archivo = version.archivo

            if version.enlace:
                evidencia.enlace = version.enlace

            evidencia.estado = "en_revision"
            evidencia.actualizado_en = timezone.now()
            evidencia.save()

            registrar_bitacora(
                request.user,
                accion="Corregir evidencia",
                descripcion=f"Se creó la versión {version.numero_version} de la evidencia {evidencia.id}.",
                tabla_afectada="evidencia_versiones",
                registro_id=version.id,
                request=request,
            )

            messages.success(request, "Corrección enviada correctamente. La evidencia queda en revisión.")
            return redirect("seguimiento:detalle_evidencia", evidencia_id=evidencia.id)

    else:
        form = CorreccionEvidenciaForm(evidencia=evidencia)

    context = {
        "form": form,
        "evidencia": evidencia,
    }

    return _render(
        request,
        [
            "seguimiento/evidencia_form.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def historial_evidencia(request, evidencia_id):
    """
    Muestra versiones y validaciones de una evidencia.
    """

    evidencias_permitidas = obtener_evidencias_por_usuario(request.user)

    evidencia = get_object_or_404(
        evidencias_permitidas,
        id=evidencia_id,
    )

    historial = obtener_historial_evidencia(evidencia)

    context = {
        "evidencia": evidencia,
        "versiones": historial["versiones"],
        "validaciones": historial["validaciones"],
    }

    return _render(
        request,
        [
            "seguimiento/evidencia_historial.html",
        ],
        context,
    )


# ============================================================
# ARTÍCULO CIENTÍFICO
# Rutas esperadas:
# /seguimiento/articulo/<proyecto_id>/
# /seguimiento/articulo/<proyecto_id>/editar/<seccion>/
# /seguimiento/articulo/<proyecto_id>/envio-revista/
# ============================================================

@login_required(login_url="accounts:login")
def articulo_seguimiento(request, proyecto_id):
    """
    Visualiza el artículo científico armado por secciones.
    """

    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        id=proyecto_id,
    )

    articulo = obtener_articulo_proyecto(proyecto)
    avance_articulo = calcular_avance_articulo(articulo)

    context = {
        "proyecto": proyecto,
        "articulo": articulo,
        "avance_articulo": avance_articulo,
    }

    return _render(
        request,
        [
            "seguimiento/articulo.html",
            "titulacion/articulo.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def editar_seccion_articulo(request, proyecto_id, seccion):
    """
    Edita una sección específica del artículo.
    """

    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        id=proyecto_id,
    )

    articulo = obtener_articulo_proyecto(proyecto)

    if not articulo:
        messages.error(
            request,
            "Este proyecto todavía no tiene un artículo creado en la base de datos."
        )
        return redirect("seguimiento:articulo", proyecto_id=proyecto.id)

    secciones_validas = [
        "titulo",
        "introduccion",
        "metodologia",
        "resultados",
        "conclusiones",
        "referencias",
    ]

    if seccion not in secciones_validas:
        messages.error(request, "La sección solicitada no es válida.")
        return redirect("seguimiento:articulo", proyecto_id=proyecto.id)

    if request.method == "POST":
        form = ArticuloSeccionForm(request.POST, articulo=articulo)

        if form.is_valid():
            seccion_form = form.cleaned_data["seccion"]
            contenido = form.cleaned_data["contenido"]

            setattr(articulo, seccion_form, contenido)
            articulo.actualizado_en = timezone.now()
            articulo.save()

            registrar_bitacora(
                request.user,
                accion="Editar sección de artículo",
                descripcion=f"Se actualizó la sección {seccion_form} del artículo {articulo.id}.",
                tabla_afectada="articulos",
                registro_id=articulo.id,
                request=request,
            )

            messages.success(request, "Sección del artículo actualizada correctamente.")
            return redirect("seguimiento:articulo", proyecto_id=proyecto.id)

    else:
        form = ArticuloSeccionForm(initial={
            "seccion": seccion,
            "contenido": getattr(articulo, seccion, "") or "",
        }, articulo=articulo)

    context = {
        "form": form,
        "proyecto": proyecto,
        "articulo": articulo,
        "seccion": seccion,
    }

    return _render(
        request,
        [
            "seguimiento/articulo_form.html",
        ],
        context,
    )


@login_required(login_url="accounts:login")
def registrar_envio_revista(request, proyecto_id):
    """
    Registra datos del envío del artículo a una revista.
    """

    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        id=proyecto_id,
    )

    articulo = obtener_articulo_proyecto(proyecto)

    if not articulo:
        messages.error(
            request,
            "Este proyecto todavía no tiene un artículo creado en la base de datos."
        )
        return redirect("seguimiento:articulo", proyecto_id=proyecto.id)

    if request.method == "POST":
        form = EnvioRevistaForm(request.POST, instance=articulo)

        if form.is_valid():
            articulo = form.save(commit=False)
            articulo.actualizado_en = timezone.now()
            articulo.save()

            registrar_bitacora(
                request.user,
                accion="Registrar envío a revista",
                descripcion=f"Se registró envío a revista del artículo {articulo.id}.",
                tabla_afectada="articulos",
                registro_id=articulo.id,
                request=request,
            )

            messages.success(request, "Envío a revista registrado correctamente.")
            return redirect("seguimiento:articulo", proyecto_id=proyecto.id)

    else:
        form = EnvioRevistaForm(instance=articulo)

    context = {
        "form": form,
        "proyecto": proyecto,
        "articulo": articulo,
    }

    return _render(
        request,
        [
            "seguimiento/articulo_form.html",
        ],
        context,
    )


# ============================================================
# CHECKLIST DE CIERRE
# Ruta esperada:
# /seguimiento/checklist/<proyecto_id>/
# ============================================================

@login_required(login_url="accounts:login")
def checklist_cierre(request, proyecto_id):
    """
    Muestra checklist de cierre.
    Bloquea cierre si no hay:
    - 8 tutorías realizadas
    - 8 evidencias validadas
    """

    proyecto = get_object_or_404(
        obtener_proyectos_del_usuario(request.user),
        id=proyecto_id,
    )

    checklist = obtener_checklist_cierre(proyecto)

    if request.method == "POST":
        form = ChecklistCierreForm(
            request.POST,
            puede_cerrar=checklist["puede_cerrar"],
        )

        if form.is_valid():
            registrar_bitacora(
                request.user,
                accion="Revisar checklist de cierre",
                descripcion=f"Se revisó checklist de cierre del proyecto {proyecto.id}.",
                tabla_afectada="proyectos_titulacion",
                registro_id=proyecto.id,
                request=request,
            )

            messages.success(request, "Checklist de cierre revisado correctamente.")
            return redirect("seguimiento:checklist_cierre", proyecto_id=proyecto.id)

    else:
        form = ChecklistCierreForm(
            puede_cerrar=checklist["puede_cerrar"],
        )

    context = {
        "form": form,
        "proyecto": proyecto,
        "checklist": checklist,
    }

    return _render(
        request,
        [
            "seguimiento/checklist_cierre.html",
        ],
        context,
    )


# ============================================================
# REPORTES
# Ruta esperada:
# /seguimiento/reportes/
# ============================================================

@login_required(login_url="accounts:login")
def reportes_seguimiento(request):
    """
    Reportes de seguimiento.
    Principalmente para coordinador y supervisor.
    """

    if not es_rol_consulta_general(request.user):
        messages.warning(
            request,
            "Solo coordinador o supervisor pueden ver reportes generales."
        )

    context = obtener_reportes_seguimiento()
    context["rol"] = obtener_nombre_rol(request.user)

    return _render(
        request,
        [
            "seguimiento/reportes.html",
        ],
        context,
    )


# ============================================================
# NOTIFICACIONES
# Ruta esperada:
# /seguimiento/notificaciones/
# ============================================================

@login_required(login_url="accounts:login")
def notificaciones_seguimiento(request):
    """
    Lista notificaciones del usuario actual.
    """

    notificaciones = obtener_notificaciones_usuario(request.user)

    context = {
        "notificaciones": notificaciones,
        "rol": obtener_nombre_rol(request.user),
    }

    return _render(
        request,
        [
            "seguimiento/notificaciones.html",
        ],
        context,
    )