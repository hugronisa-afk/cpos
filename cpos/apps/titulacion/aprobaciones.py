"""Flujo institucional y versionado de aprobaciones académicas."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import EstadoTitulacion
from apps.accounts.services import registrar_bitacora, usuario_tiene_permiso

from .modalidades import modalidad_disponible
from .models import (
    Aprobacion,
    ArchivoProyecto,
    DocumentoProcesoAprobacion,
    EstadoAprobacion,
    EstadoCambioModalidad,
    EstadoCambioTema,
    EstadoPasoAprobacion,
    EstadoProcesoAprobacion,
    EstadoProyecto,
    ModalidadProyecto,
    PasoAprobacion,
    ProcesoAprobacion,
    SolicitudCambioModalidad,
    SolicitudCambioTema,
    TipoArchivo,
    TipoDocumentoAprobacion,
    TipoProcesoAprobacion,
)


PLANTILLAS_PASOS = {
    TipoProcesoAprobacion.PROYECTO: (
        {
            "codigo": "visto_bueno_inicial",
            "nombre": "Visto bueno inicial",
            "instancia": "Coordinación del programa",
            "rol_responsable": "coordinador",
        },
        {
            "codigo": "revision_comision",
            "nombre": "Revisión de comisión",
            "instancia": "Comisión académica de titulación",
            "rol_responsable": "coordinador",
        },
        {
            "codigo": "aprobacion_supervisor",
            "nombre": "Aprobación institucional final",
            "instancia": "Supervisión general",
            "rol_responsable": "supervisor",
        },
    ),
    TipoProcesoAprobacion.CAMBIO_TEMA: (
        {
            "codigo": "revision_sustento",
            "nombre": "Revisión del sustento",
            "instancia": "Coordinación del programa",
            "rol_responsable": "coordinador",
        },
        {
            "codigo": "unidad_titulacion",
            "nombre": "Revisión de unidad de titulación",
            "instancia": "Unidad de titulación",
            "rol_responsable": "coordinador",
        },
        {
            "codigo": "consejo_posgrado",
            "nombre": "Revisión del consejo de posgrado",
            "instancia": "Consejo de posgrado",
            "rol_responsable": "supervisor",
        },
        {
            "codigo": "aprobacion_supervisor",
            "nombre": "Aprobación institucional final",
            "instancia": "Supervisión general",
            "rol_responsable": "supervisor",
        },
    ),
    TipoProcesoAprobacion.CAMBIO_MODALIDAD: (
        {
            "codigo": "revision_sustento",
            "nombre": "Revisión del sustento",
            "instancia": "Coordinación del programa",
            "rol_responsable": "coordinador",
        },
        {
            "codigo": "unidad_titulacion",
            "nombre": "Revisión de unidad de titulación",
            "instancia": "Unidad de titulación",
            "rol_responsable": "coordinador",
        },
        {
            "codigo": "consejo_posgrado",
            "nombre": "Revisión del consejo de posgrado",
            "instancia": "Consejo de posgrado",
            "rol_responsable": "supervisor",
        },
        {
            "codigo": "aprobacion_supervisor",
            "nombre": "Aprobación institucional final",
            "instancia": "Supervisión general",
            "rol_responsable": "supervisor",
        },
    ),
}


def _rol_usuario(usuario):
    return str(getattr(getattr(usuario, "rol", None), "nombre", "")).strip().lower()


def procesos_visibles(usuario):
    from .services import proyectos_visibles

    return ProcesoAprobacion.objects.select_related(
        "proyecto",
        "proyecto__maestrante__usuario",
        "proyecto__maestrante__programa",
        "creado_por",
    ).filter(proyecto__in=proyectos_visibles(usuario))


def obtener_proceso_visible(usuario, pk):
    try:
        return procesos_visibles(usuario).get(pk=pk)
    except ProcesoAprobacion.DoesNotExist as exc:
        raise PermissionDenied("No tiene acceso a este proceso de aprobación.") from exc


def proceso_activo_proyecto(proyecto):
    return (
        ProcesoAprobacion.objects.filter(
            proyecto=proyecto,
            estado=EstadoProcesoAprobacion.EN_CURSO,
        )
        .order_by("-fecha_creacion", "-id")
        .first()
    )


def _crear_pasos(proceso):
    pasos = []
    for orden, definicion in enumerate(PLANTILLAS_PASOS[proceso.tipo], start=1):
        pasos.append(
            PasoAprobacion(
                proceso=proceso,
                orden=orden,
                estado=(
                    EstadoPasoAprobacion.ACTIVO
                    if orden == 1
                    else EstadoPasoAprobacion.PENDIENTE
                ),
                **definicion,
            )
        )
    PasoAprobacion.objects.bulk_create(pasos)
    return list(proceso.pasos.all())


def _registrar_pendiente(paso):
    return Aprobacion.objects.create(
        proyecto=paso.proceso.proyecto,
        tipo_aprobacion=paso.proceso.tipo,
        referencia_tabla="pasos_aprobacion",
        referencia_id=paso.pk,
        estado=EstadoAprobacion.PENDIENTE,
    )


def _registrar_evento(request, usuario, accion, tabla, registro_id, descripcion):
    return registrar_bitacora(
        usuario=usuario,
        modulo="titulacion",
        accion=accion,
        tabla_afectada=tabla,
        registro_id=registro_id,
        descripcion=descripcion,
        request=request,
    )


@transaction.atomic
def iniciar_revision_proyecto(proyecto, actor, request=None):
    from .services import puede_editar_proyecto

    proyecto = proyecto.__class__.objects.select_for_update().select_related(
        "maestrante"
    ).get(pk=proyecto.pk)
    if not puede_editar_proyecto(actor, proyecto):
        raise PermissionDenied("No puede enviar este proyecto a revisión.")
    if proceso_activo_proyecto(proyecto):
        raise ValidationError("El proyecto ya tiene una revisión en curso.")

    documento_word = ArchivoProyecto.objects.filter(
        proyecto=proyecto,
        tipo_archivo=TipoArchivo.WORD,
    ).order_by("-fecha_creacion", "-id").first()
    documento_pdf = ArchivoProyecto.objects.filter(
        proyecto=proyecto,
        tipo_archivo=TipoArchivo.PDF,
    ).order_by("-fecha_creacion", "-id").first()
    faltantes = []
    if not documento_word:
        faltantes.append("Word editable")
    if not documento_pdf:
        faltantes.append("PDF")
    if faltantes:
        raise ValidationError(
            "Antes de enviar debe subir: " + " y ".join(faltantes) + "."
        )

    ultima_version = ProcesoAprobacion.objects.filter(
        tipo=TipoProcesoAprobacion.PROYECTO,
        referencia_tabla="proyectos_titulacion",
        referencia_id=proyecto.pk,
    ).aggregate(mayor=Max("numero_version"))["mayor"]
    proceso = ProcesoAprobacion.objects.create(
        proyecto=proyecto,
        tipo=TipoProcesoAprobacion.PROYECTO,
        referencia_tabla="proyectos_titulacion",
        referencia_id=proyecto.pk,
        numero_version=(ultima_version or 0) + 1,
        creado_por=actor,
    )
    DocumentoProcesoAprobacion.objects.bulk_create(
        (
            DocumentoProcesoAprobacion(
                proceso=proceso,
                archivo=documento_word,
                tipo_documento=TipoDocumentoAprobacion.WORD,
            ),
            DocumentoProcesoAprobacion(
                proceso=proceso,
                archivo=documento_pdf,
                tipo_documento=TipoDocumentoAprobacion.PDF,
            ),
        )
    )
    pasos = _crear_pasos(proceso)
    _registrar_pendiente(pasos[0])

    proyecto.estado = EstadoProyecto.EN_REVISION
    proyecto.observaciones = None
    proyecto.actualizado_por = actor
    proyecto.save(
        update_fields=(
            "estado",
            "observaciones",
            "actualizado_por",
            "fecha_actualizacion",
        )
    )
    proyecto.maestrante.estado_titulacion = EstadoTitulacion.EN_REVISION
    proyecto.maestrante.save(
        update_fields=("estado_titulacion", "fecha_actualizacion")
    )
    _registrar_evento(
        request,
        actor,
        "iniciar_revision_formal",
        "procesos_aprobacion",
        proceso.pk,
        f"Se inició la revisión formal versión {proceso.numero_version}.",
    )
    return proceso


@transaction.atomic
def iniciar_proceso_cambio(solicitud, tipo, actor, request=None):
    if tipo not in {
        TipoProcesoAprobacion.CAMBIO_TEMA,
        TipoProcesoAprobacion.CAMBIO_MODALIDAD,
    }:
        raise ValidationError("Tipo de solicitud no permitido.")
    if proceso_activo_proyecto(solicitud.proyecto):
        raise ValidationError(
            "El proyecto ya tiene otro proceso de aprobación en curso."
        )
    tabla = (
        "solicitudes_cambio_tema"
        if tipo == TipoProcesoAprobacion.CAMBIO_TEMA
        else "solicitudes_cambio_modalidad"
    )
    proceso = ProcesoAprobacion.objects.create(
        proyecto=solicitud.proyecto,
        tipo=tipo,
        referencia_tabla=tabla,
        referencia_id=solicitud.pk,
        numero_version=1,
        creado_por=actor,
    )
    pasos = _crear_pasos(proceso)
    _registrar_pendiente(pasos[0])
    if isinstance(solicitud, SolicitudCambioTema):
        solicitud.estado = EstadoCambioTema.EN_REVISION
        solicitud.save(update_fields=("estado", "fecha_actualizacion"))
    _registrar_evento(
        request,
        actor,
        "iniciar_aprobacion_cambio",
        "procesos_aprobacion",
        proceso.pk,
        f"Se inició el proceso formal de {proceso.get_tipo_display().lower()}.",
    )
    return proceso


def puede_resolver_paso(usuario, paso):
    if paso.estado != EstadoPasoAprobacion.ACTIVO:
        return False
    if paso.proceso.estado != EstadoProcesoAprobacion.EN_CURSO:
        return False
    rol = _rol_usuario(usuario)
    if rol != paso.rol_responsable:
        return False
    if rol == "coordinador" and (
        paso.proceso.proyecto.maestrante.programa.coordinador_id != usuario.pk
    ):
        return False
    permiso = (
        "APROBACION_COORDINACION"
        if rol == "coordinador"
        else "APROBACION_SUPERVISION"
    )
    return usuario_tiene_permiso(usuario, permiso)


def _resolver_aprobacion_paso(paso, actor, estado, observaciones):
    aprobacion = Aprobacion.objects.filter(
        proyecto=paso.proceso.proyecto,
        tipo_aprobacion=paso.proceso.tipo,
        referencia_tabla="pasos_aprobacion",
        referencia_id=paso.pk,
        estado=EstadoAprobacion.PENDIENTE,
    ).order_by("-fecha_creacion", "-id").first()
    if not aprobacion:
        aprobacion = Aprobacion(
            proyecto=paso.proceso.proyecto,
            tipo_aprobacion=paso.proceso.tipo,
            referencia_tabla="pasos_aprobacion",
            referencia_id=paso.pk,
        )
    aprobacion.aprobado_por = actor
    aprobacion.estado = estado
    aprobacion.observaciones = observaciones
    aprobacion.save()


def _rechazar_referencia(proceso, actor, observaciones):
    if proceso.tipo == TipoProcesoAprobacion.CAMBIO_TEMA:
        solicitud = SolicitudCambioTema.objects.select_for_update().get(
            pk=proceso.referencia_id
        )
        solicitud.estado = EstadoCambioTema.RECHAZADA
        solicitud.save(update_fields=("estado", "fecha_actualizacion"))
    elif proceso.tipo == TipoProcesoAprobacion.CAMBIO_MODALIDAD:
        solicitud = SolicitudCambioModalidad.objects.select_for_update().get(
            pk=proceso.referencia_id
        )
        solicitud.estado = EstadoCambioModalidad.RECHAZADA
        solicitud.resuelto_por = actor
        solicitud.observaciones_resolucion = observaciones
        solicitud.fecha_resolucion = timezone.now()
        solicitud.save()


def _aplicar_aprobacion_final(proceso, actor):
    proyecto = proceso.proyecto.__class__.objects.select_for_update().select_related(
        "maestrante__programa"
    ).get(pk=proceso.proyecto_id)
    if proceso.tipo == TipoProcesoAprobacion.PROYECTO:
        proyecto.estado = EstadoProyecto.APROBADO
        proyecto.fecha_aprobacion = proyecto.fecha_aprobacion or timezone.localdate()
        proyecto.observaciones = None
        proyecto.actualizado_por = actor
        proyecto.save()
        proyecto.maestrante.estado_titulacion = EstadoTitulacion.PROYECTO_APROBADO
        proyecto.maestrante.save(
            update_fields=("estado_titulacion", "fecha_actualizacion")
        )
    elif proceso.tipo == TipoProcesoAprobacion.CAMBIO_TEMA:
        solicitud = SolicitudCambioTema.objects.select_for_update().get(
            pk=proceso.referencia_id
        )
        solicitud.estado = EstadoCambioTema.APROBADA
        solicitud.save(update_fields=("estado", "fecha_actualizacion"))
        proyecto.tema = solicitud.tema_propuesto
        proyecto.actualizado_por = actor
        proyecto.save(update_fields=("tema", "actualizado_por", "fecha_actualizacion"))
    elif proceso.tipo == TipoProcesoAprobacion.CAMBIO_MODALIDAD:
        solicitud = SolicitudCambioModalidad.objects.select_for_update().get(
            pk=proceso.referencia_id
        )
        if not modalidad_disponible(
            proyecto.maestrante.programa,
            solicitud.modalidad_propuesta,
        ):
            raise ValidationError("La modalidad propuesta ya no está disponible.")
        solicitud.estado = EstadoCambioModalidad.APROBADA
        solicitud.resuelto_por = actor
        solicitud.fecha_resolucion = timezone.now()
        solicitud.save()
        proyecto.modalidad = solicitud.modalidad_propuesta
        proyecto.actualizado_por = actor
        proyecto.save(
            update_fields=("modalidad", "actualizado_por", "fecha_actualizacion")
        )
        if proyecto.modalidad != ModalidadProyecto.ARTICULO:
            proyecto.articulos.filter(esta_activo=True).update(
                esta_activo=False,
                fecha_actualizacion=timezone.now(),
            )


@transaction.atomic
def resolver_paso(paso, actor, decision, observaciones=None, request=None):
    paso = PasoAprobacion.objects.select_for_update().select_related(
        "proceso",
        "proceso__proyecto__maestrante__programa",
    ).get(pk=paso.pk)
    if not puede_resolver_paso(actor, paso):
        raise PermissionDenied("No puede resolver esta etapa de aprobación.")
    if decision not in {"aprobar", "observar", "rechazar"}:
        raise ValidationError("Decisión no permitida.")
    observaciones = str(observaciones or "").strip() or None
    if decision in {"observar", "rechazar"} and not observaciones:
        raise ValidationError("Debe registrar observaciones para esta decisión.")
    if decision == "observar" and paso.proceso.tipo != TipoProcesoAprobacion.PROYECTO:
        raise ValidationError("Las solicitudes de cambio deben aprobarse o rechazarse.")

    ahora = timezone.now()
    mapa_paso = {
        "aprobar": EstadoPasoAprobacion.APROBADO,
        "observar": EstadoPasoAprobacion.OBSERVADO,
        "rechazar": EstadoPasoAprobacion.RECHAZADO,
    }
    mapa_aprobacion = {
        "aprobar": EstadoAprobacion.APROBADO,
        "observar": EstadoAprobacion.OBSERVADO,
        "rechazar": EstadoAprobacion.RECHAZADO,
    }
    paso.estado = mapa_paso[decision]
    paso.resuelto_por = actor
    paso.observaciones = observaciones
    paso.fecha_resolucion = ahora
    paso.save()
    _resolver_aprobacion_paso(
        paso,
        actor,
        mapa_aprobacion[decision],
        observaciones,
    )

    proceso = paso.proceso
    if decision == "aprobar":
        siguiente = proceso.pasos.filter(orden__gt=paso.orden).order_by("orden").first()
        if siguiente:
            siguiente.estado = EstadoPasoAprobacion.ACTIVO
            siguiente.save(update_fields=("estado", "fecha_actualizacion"))
            proceso.paso_actual = siguiente.orden
            proceso.save(update_fields=("paso_actual", "fecha_actualizacion"))
            _registrar_pendiente(siguiente)
        else:
            _aplicar_aprobacion_final(proceso, actor)
            proceso.estado = EstadoProcesoAprobacion.APROBADO
            proceso.fecha_finalizacion = ahora
            proceso.save()
    elif decision == "observar":
        proceso.estado = EstadoProcesoAprobacion.OBSERVADO
        proceso.fecha_finalizacion = ahora
        proceso.save()
        proyecto = proceso.proyecto
        proyecto.estado = EstadoProyecto.OBSERVADO
        proyecto.observaciones = observaciones
        proyecto.actualizado_por = actor
        proyecto.save()
        proyecto.maestrante.estado_titulacion = EstadoTitulacion.PROYECTO_BORRADOR
        proyecto.maestrante.save(
            update_fields=("estado_titulacion", "fecha_actualizacion")
        )
    else:
        proceso.estado = EstadoProcesoAprobacion.RECHAZADO
        proceso.fecha_finalizacion = ahora
        proceso.save()
        if proceso.tipo == TipoProcesoAprobacion.PROYECTO:
            proyecto = proceso.proyecto
            proyecto.estado = EstadoProyecto.RECHAZADO
            proyecto.observaciones = observaciones
            proyecto.actualizado_por = actor
            proyecto.save()
            proyecto.maestrante.estado_titulacion = EstadoTitulacion.PROYECTO_BORRADOR
            proyecto.maestrante.save(
                update_fields=("estado_titulacion", "fecha_actualizacion")
            )
        else:
            _rechazar_referencia(proceso, actor, observaciones)

    _registrar_evento(
        request,
        actor,
        "resolver_paso_aprobacion",
        "pasos_aprobacion",
        paso.pk,
        f"{paso.nombre}: {decision}.",
    )
    return proceso
