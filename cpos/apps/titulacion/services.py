"""Reglas de alcance y transición del módulo de Titulación.

Los permisos de Accounts habilitan capacidades generales. Estas reglas agregan
el alcance académico: un maestrante solo ve lo suyo, un tutor solo sus
asignaciones, un coordinador solo sus programas y un supervisor solo consulta.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import EstadoTitulacion
from apps.accounts.services import registrar_bitacora, usuario_tiene_permiso

from .models import (
    Aprobacion,
    ArchivoProyecto,
    AsignacionTutor,
    EstadoAprobacion,
    EstadoAsignacion,
    EstadoCambioTema,
    EstadoProyecto,
    EstadoReprogramacion,
    EstadoTutoria,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    Tutoria,
)


ROLES = {"maestrante", "tutor", "coordinador", "supervisor"}


def rol_usuario(usuario) -> str:
    rol = getattr(getattr(usuario, "rol", None), "nombre", "")
    return str(rol).strip().lower()


def es_supervisor(usuario) -> bool:
    return rol_usuario(usuario) == "supervisor"


def puede_escribir(usuario) -> bool:
    """Supervisor es lectura aunque Accounts tenga permisos excesivos."""
    return rol_usuario(usuario) in {"maestrante", "tutor", "coordinador"}


def proyectos_visibles(usuario) -> QuerySet:
    consulta = ProyectoTitulacion.objects.select_related(
        "maestrante",
        "maestrante__usuario",
        "maestrante__programa",
        "maestrante__cohorte",
    ).filter(esta_activo=True)
    rol = rol_usuario(usuario)
    if rol == "maestrante":
        return consulta.filter(maestrante__usuario_id=usuario.pk)
    if rol == "tutor":
        return consulta.filter(
            asignaciones_tutor__tutor__usuario_id=usuario.pk,
            asignaciones_tutor__estado=EstadoAsignacion.ACTIVO,
        ).distinct()
    if rol == "coordinador":
        return consulta.filter(maestrante__programa__coordinador_id=usuario.pk)
    if rol == "supervisor":
        return consulta
    return consulta.none()


def obtener_proyecto_visible(usuario, pk: int) -> ProyectoTitulacion:
    try:
        return proyectos_visibles(usuario).get(pk=pk)
    except ProyectoTitulacion.DoesNotExist as exc:
        raise PermissionDenied("No tiene acceso a este proyecto.") from exc


def puede_crear_proyecto(usuario) -> bool:
    return (
        rol_usuario(usuario) == "maestrante"
        and usuario_tiene_permiso(usuario, "PROYECTO_CREAR")
        and hasattr(usuario, "perfil_maestrante")
        and not ProyectoTitulacion.objects.filter(
            maestrante__usuario_id=usuario.pk,
            esta_activo=True,
        ).exists()
    )


def puede_editar_proyecto(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "maestrante"
        and proyecto.maestrante.usuario_id == usuario.pk
        and proyecto.estado in {EstadoProyecto.BORRADOR, EstadoProyecto.OBSERVADO}
        and usuario_tiene_permiso(usuario, "PROYECTO_EDITAR")
    )


def puede_revisar_proyecto(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) in {"tutor", "coordinador"}
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "PROYECTO_REVISAR")
    )


def puede_aprobar_proyecto(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "coordinador"
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "PROYECTO_APROBAR")
    )


def puede_gestionar_programacion(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "coordinador"
        and proyecto.estado == EstadoProyecto.APROBADO
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "TUTORIA_PROGRAMAR")
    )


def puede_registrar_sesion(usuario, tutoria) -> bool:
    rol = rol_usuario(usuario)
    if rol == "tutor":
        return tutoria.tutor.usuario_id == usuario.pk
    if rol == "coordinador":
        return proyectos_visibles(usuario).filter(pk=tutoria.proyecto_id).exists()
    return False


def puede_editar_articulo(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "maestrante"
        and proyecto.maestrante.usuario_id == usuario.pk
        and usuario_tiene_permiso(usuario, "ARTICULO_EDITAR")
    )


def puede_revisar_articulo(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) in {"tutor", "coordinador"}
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "ARTICULO_REVISAR")
    )


def puede_revisar_archivo(usuario, archivo: ArchivoProyecto) -> bool:
    rol = rol_usuario(usuario)
    if rol == "tutor":
        return archivo.proyecto.asignaciones_tutor.filter(
            tutor__usuario_id=usuario.pk,
            estado=EstadoAsignacion.ACTIVO,
        ).exists()
    if rol == "coordinador":
        return proyectos_visibles(usuario).filter(pk=archivo.proyecto_id).exists()
    return False


def puede_solicitar_cambio_tema(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) in {"maestrante", "tutor"}
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "CAMBIO_TEMA_SOLICITAR")
        and not proyecto.solicitudes_cambio_tema.filter(
            estado__in=[EstadoCambioTema.PENDIENTE, EstadoCambioTema.EN_REVISION]
        ).exists()
    )


def puede_revisar_cambio_tema(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "coordinador"
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "CAMBIO_TEMA_REVISAR")
    )


def registrar_evento(request, *, accion, tabla, registro_id, descripcion):
    return registrar_bitacora(
        usuario=request.user,
        modulo="titulacion",
        accion=accion,
        tabla_afectada=tabla,
        registro_id=registro_id,
        descripcion=descripcion,
        request=request,
    )


def registrar_solicitud_aprobacion(*, proyecto, tipo, tabla, registro_id):
    aprobacion, _ = Aprobacion.objects.get_or_create(
        proyecto=proyecto,
        tipo_aprobacion=tipo,
        referencia_tabla=tabla,
        referencia_id=registro_id,
        estado=EstadoAprobacion.PENDIENTE,
    )
    return aprobacion


def _resolver_aprobacion(*, proyecto, tipo, tabla, registro_id, actor, estado, observaciones=None):
    aprobacion = Aprobacion.objects.filter(
        proyecto=proyecto,
        tipo_aprobacion=tipo,
        referencia_tabla=tabla,
        referencia_id=registro_id,
        estado=EstadoAprobacion.PENDIENTE,
    ).order_by("-fecha_creacion").first()
    if aprobacion is None:
        aprobacion = Aprobacion(
            proyecto=proyecto,
            tipo_aprobacion=tipo,
            referencia_tabla=tabla,
            referencia_id=registro_id,
        )
    aprobacion.aprobado_por = actor
    aprobacion.estado = estado
    aprobacion.observaciones = str(observaciones or "").strip() or None
    aprobacion.save()
    return aprobacion


@transaction.atomic
def enviar_proyecto_revision(proyecto, actor, request=None):
    if not puede_editar_proyecto(actor, proyecto):
        raise PermissionDenied("No puede enviar este proyecto a revisión.")
    proyecto.estado = EstadoProyecto.EN_REVISION
    proyecto.actualizado_por = actor
    proyecto.save(update_fields=("estado", "actualizado_por", "fecha_actualizacion"))
    proyecto.maestrante.estado_titulacion = EstadoTitulacion.EN_REVISION
    proyecto.maestrante.save(update_fields=("estado_titulacion", "fecha_actualizacion"))
    registrar_solicitud_aprobacion(
        proyecto=proyecto,
        tipo="proyecto",
        tabla="proyectos_titulacion",
        registro_id=proyecto.pk,
    )
    if request:
        registrar_evento(request, accion="enviar_proyecto_revision", tabla="proyectos_titulacion", registro_id=proyecto.pk, descripcion="El proyecto fue enviado a revisión.")
    return proyecto


@transaction.atomic
def resolver_revision_proyecto(proyecto, actor, estado, observaciones, request=None):
    if proyecto.estado != EstadoProyecto.EN_REVISION:
        raise ValidationError("Solo se puede resolver un proyecto en revisión.")
    if estado == EstadoProyecto.APROBADO:
        permitido = puede_aprobar_proyecto(actor, proyecto)
    else:
        permitido = puede_revisar_proyecto(actor, proyecto)
    if not permitido:
        raise PermissionDenied("No puede resolver la revisión de este proyecto.")
    if estado not in {EstadoProyecto.OBSERVADO, EstadoProyecto.RECHAZADO, EstadoProyecto.APROBADO}:
        raise ValidationError("Estado de revisión no permitido.")
    if estado != EstadoProyecto.APROBADO and not str(observaciones or "").strip():
        raise ValidationError("Debe registrar observaciones.")
    proyecto.estado = estado
    proyecto.observaciones = str(observaciones or "").strip() or None
    proyecto.actualizado_por = actor
    if estado == EstadoProyecto.APROBADO:
        proyecto.fecha_aprobacion = proyecto.fecha_aprobacion or timezone.localdate()
    proyecto.save()
    mapa = {
        EstadoProyecto.OBSERVADO: EstadoTitulacion.PROYECTO_BORRADOR,
        EstadoProyecto.RECHAZADO: EstadoTitulacion.PROYECTO_BORRADOR,
        EstadoProyecto.APROBADO: EstadoTitulacion.PROYECTO_APROBADO,
    }
    proyecto.maestrante.estado_titulacion = mapa[estado]
    proyecto.maestrante.save(update_fields=("estado_titulacion", "fecha_actualizacion"))
    _resolver_aprobacion(
        proyecto=proyecto,
        tipo="proyecto",
        tabla="proyectos_titulacion",
        registro_id=proyecto.pk,
        actor=actor,
        estado=EstadoAprobacion.APROBADO if estado == EstadoProyecto.APROBADO else EstadoAprobacion.OBSERVADO if estado == EstadoProyecto.OBSERVADO else EstadoAprobacion.RECHAZADO,
        observaciones=proyecto.observaciones,
    )
    if request:
        registrar_evento(request, accion="resolver_revision_proyecto", tabla="proyectos_titulacion", registro_id=proyecto.pk, descripcion=f"El proyecto cambió a estado {estado}.")
    return proyecto


@transaction.atomic
def asignar_tutor(proyecto, tutor, actor, motivo=None, request=None):
    if rol_usuario(actor) != "coordinador" or not usuario_tiene_permiso(actor, "ASIGNACION_TUTOR_CREAR"):
        raise PermissionDenied("No puede asignar tutores.")
    if not proyectos_visibles(actor).filter(pk=proyecto.pk).exists():
        raise PermissionDenied("El proyecto no pertenece a su programa.")
    if proyecto.estado != EstadoProyecto.APROBADO:
        raise ValidationError("El proyecto debe estar aprobado antes de asignar tutor.")
    anterior = proyecto.asignaciones_tutor.select_for_update().filter(estado=EstadoAsignacion.ACTIVO).first()
    if anterior:
        if anterior.tutor_id == tutor.pk:
            raise ValidationError("Este tutor ya está asignado al proyecto.")
        anterior.estado = EstadoAsignacion.REEMPLAZADO
        anterior.motivo_cambio = str(motivo or "").strip() or "Cambio de tutor"
        anterior.save()
    asignacion = AsignacionTutor.objects.create(
        proyecto=proyecto,
        tutor=tutor,
        asignado_por=actor,
        motivo_cambio=str(motivo or "").strip() or None,
    )
    proyecto.maestrante.estado_titulacion = EstadoTitulacion.TUTOR_ASIGNADO
    proyecto.maestrante.save(update_fields=("estado_titulacion", "fecha_actualizacion"))
    if request:
        registrar_evento(request, accion="asignar_tutor", tabla="asignaciones_tutor", registro_id=asignacion.pk, descripcion=f"Tutor asignado al proyecto {proyecto.pk}.")
    return asignacion


@transaction.atomic
def resolver_reprogramacion(reprogramacion, actor, aprobar, request=None):
    if rol_usuario(actor) != "coordinador" or not proyectos_visibles(actor).filter(pk=reprogramacion.tutoria.proyecto_id).exists():
        raise PermissionDenied("No puede resolver esta reprogramación.")
    if reprogramacion.estado != EstadoReprogramacion.PENDIENTE:
        raise ValidationError("La solicitud ya fue resuelta.")
    reprogramacion.estado = EstadoReprogramacion.APROBADA if aprobar else EstadoReprogramacion.RECHAZADA
    reprogramacion.aprobado_por = actor
    reprogramacion.save()
    if aprobar:
        tutoria = reprogramacion.tutoria
        tutoria.fecha = reprogramacion.fecha_nueva
        tutoria.hora_inicio = reprogramacion.hora_inicio_nueva
        tutoria.hora_fin = reprogramacion.hora_fin_nueva
        tutoria.estado = EstadoTutoria.REPROGRAMADA
        tutoria.save()
    _resolver_aprobacion(
        proyecto=reprogramacion.tutoria.proyecto,
        tipo="reprogramacion",
        tabla="reprogramaciones_tutoria",
        registro_id=reprogramacion.pk,
        actor=actor,
        estado=EstadoAprobacion.APROBADO if aprobar else EstadoAprobacion.RECHAZADO,
    )
    if request:
        registrar_evento(request, accion="resolver_reprogramacion", tabla="reprogramaciones_tutoria", registro_id=reprogramacion.pk, descripcion=f"Reprogramación {reprogramacion.estado}.")
    return reprogramacion


@transaction.atomic
def resolver_cambio_tema(solicitud: SolicitudCambioTema, actor, aprobar, request=None):
    if not puede_revisar_cambio_tema(actor, solicitud.proyecto):
        raise PermissionDenied("No puede resolver esta solicitud.")
    if solicitud.estado not in {EstadoCambioTema.PENDIENTE, EstadoCambioTema.EN_REVISION}:
        raise ValidationError("La solicitud ya fue resuelta.")
    solicitud.estado = EstadoCambioTema.APROBADA if aprobar else EstadoCambioTema.RECHAZADA
    solicitud.save()
    if aprobar:
        solicitud.proyecto.tema = solicitud.tema_propuesto
        solicitud.proyecto.actualizado_por = actor
        solicitud.proyecto.save()
    aprobacion = _resolver_aprobacion(
        proyecto=solicitud.proyecto,
        tipo="cambio_tema",
        tabla="solicitudes_cambio_tema",
        registro_id=solicitud.pk,
        actor=actor,
        estado=EstadoAprobacion.APROBADO if aprobar else EstadoAprobacion.RECHAZADO,
    )
    if request:
        registrar_evento(request, accion="resolver_cambio_tema", tabla="solicitudes_cambio_tema", registro_id=solicitud.pk, descripcion=f"Solicitud de cambio de tema {solicitud.estado}.")
    return aprobacion


@transaction.atomic
def resolver_revision_archivo(archivo, actor, estado, observaciones, request=None):
    if not puede_revisar_archivo(actor, archivo):
        raise PermissionDenied("No puede revisar este archivo.")
    if estado not in {
        EstadoAprobacion.APROBADO,
        EstadoAprobacion.OBSERVADO,
        EstadoAprobacion.RECHAZADO,
    }:
        raise ValidationError("Estado de revisión no permitido.")
    if estado != EstadoAprobacion.APROBADO and not str(observaciones or "").strip():
        raise ValidationError("Debe registrar observaciones.")
    aprobacion = _resolver_aprobacion(
        proyecto=archivo.proyecto,
        tipo="archivo_proyecto",
        tabla="archivos_proyecto",
        registro_id=archivo.pk,
        actor=actor,
        estado=estado,
        observaciones=observaciones,
    )
    if request:
        registrar_evento(
            request,
            accion="revisar_archivo_proyecto",
            tabla="archivos_proyecto",
            registro_id=archivo.pk,
            descripcion=f"El archivo fue marcado como {estado}.",
        )
    return aprobacion


def resumen_evidencias(proyecto):
    """Contrato opcional con Seguimiento, sin duplicar sus modelos.

    Persona 3 puede exponer ``obtener_resumen_evidencias_proyecto``. Mientras
    no exista, Titulación muestra el estado de integración sin fingir cifras.
    """
    try:
        from apps.seguimiento.services import obtener_resumen_evidencias_proyecto
    except (ImportError, AttributeError):
        return {"integrado": False, "total": None, "validadas": None}
    return {"integrado": True, **obtener_resumen_evidencias_proyecto(proyecto)}
