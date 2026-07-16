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

from .modalidades import modalidad_disponible
from .models import (
    Aprobacion,
    ArchivoProyecto,
    AsignacionTutor,
    AutorizacionNovenaTutoria,
    DisponibilidadTutor,
    EntregaEtapa,
    EstadoAprobacion,
    EstadoAsignacion,
    EstadoCambioTema,
    EstadoCambioModalidad,
    EstadoEtapaProducto,
    EstadoOnboarding,
    EstadoProyecto,
    EstadoReprogramacion,
    EstadoSolicitudCambioTutor,
    EstadoTutoria,
    EtapaProducto,
    ModalidadConfigurada,
    ModalidadProyecto,
    OnboardingMaestrante,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTutor,
    SolicitudCambioTema,
    SolicitudCambioModalidad,
    Tutoria,
    Tutor,
    TutorPrograma,
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
        ).exclude(estado=EstadoProyecto.RECHAZADO).exists()
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
        rol_usuario(usuario) == "supervisor"
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "APROBACION_SUPERVISION")
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
        and proyecto.modalidad == ModalidadProyecto.ARTICULO
        and usuario_tiene_permiso(usuario, "ARTICULO_EDITAR")
    )


def puede_revisar_articulo(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) in {"tutor", "coordinador"}
        and proyecto.modalidad == ModalidadProyecto.ARTICULO
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
        and proyecto.estado == EstadoProyecto.APROBADO
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


def puede_solicitar_cambio_modalidad(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) in {"maestrante", "tutor"}
        and proyecto.estado == EstadoProyecto.APROBADO
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "CAMBIO_MODALIDAD_SOLICITAR")
        and not proyecto.solicitudes_cambio_modalidad.filter(
            estado=EstadoCambioModalidad.PENDIENTE
        ).exists()
    )


def puede_revisar_cambio_modalidad(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "coordinador"
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "CAMBIO_MODALIDAD_REVISAR")
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


def _validar_tutor_elegible(proyecto, tutor):
    if (
        tutor.estado != "disponible"
        or not tutor.usuario.is_active
        or rol_usuario(tutor.usuario) != "tutor"
    ):
        raise ValidationError("El tutor seleccionado no está disponible.")
    vinculo = TutorPrograma.objects.filter(
        tutor=tutor,
        programa_id=proyecto.maestrante.programa_id,
        esta_activo=True,
    ).first()
    if vinculo is None:
        raise ValidationError("El tutor no está habilitado para este programa.")
    if not DisponibilidadTutor.objects.filter(tutor=tutor, esta_activa=True).exists():
        raise ValidationError("El tutor no tiene disponibilidad horaria registrada.")
    carga = AsignacionTutor.objects.filter(
        tutor=tutor,
        estado=EstadoAsignacion.ACTIVO,
    ).count()
    if carga >= vinculo.cupo_maximo:
        raise ValidationError("El tutor alcanzó su cupo máximo de proyectos activos.")
    return vinculo


@transaction.atomic
def asignar_tutor(proyecto, tutor, actor, motivo=None, request=None):
    ProyectoTitulacion.objects.select_for_update().filter(pk=proyecto.pk).exists()
    Tutor.objects.select_for_update().filter(pk=tutor.pk).exists()
    if rol_usuario(actor) != "coordinador" or not usuario_tiene_permiso(actor, "ASIGNACION_TUTOR_CREAR"):
        raise PermissionDenied("No puede asignar tutores.")
    if not proyectos_visibles(actor).filter(pk=proyecto.pk).exists():
        raise PermissionDenied("El proyecto no pertenece a su programa.")
    if proyecto.estado != EstadoProyecto.APROBADO:
        raise ValidationError("El proyecto debe estar aprobado antes de asignar tutor.")
    _validar_tutor_elegible(proyecto, tutor)
    anterior = proyecto.asignaciones_tutor.select_for_update().filter(estado=EstadoAsignacion.ACTIVO).first()
    if anterior:
        raise ValidationError(
            "El proyecto ya tiene tutor. Use la solicitud formal de cambio."
        )
    asignacion = AsignacionTutor.objects.create(
        proyecto=proyecto,
        tutor=tutor,
        asignado_por=actor,
        motivo_cambio=None,
    )
    proyecto.maestrante.estado_titulacion = EstadoTitulacion.TUTOR_ASIGNADO
    proyecto.maestrante.save(update_fields=("estado_titulacion", "fecha_actualizacion"))
    if request:
        registrar_evento(request, accion="asignar_tutor", tabla="asignaciones_tutor", registro_id=asignacion.pk, descripcion=f"Tutor asignado al proyecto {proyecto.pk}.")
    return asignacion


def puede_solicitar_cambio_tutor(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) in {"maestrante", "tutor"}
        and proyecto.estado == EstadoProyecto.APROBADO
        and proyectos_visibles(usuario).filter(pk=proyecto.pk).exists()
        and usuario_tiene_permiso(usuario, "CAMBIO_TUTOR_SOLICITAR")
        and proyecto.asignaciones_tutor.filter(
            estado=EstadoAsignacion.ACTIVO
        ).exists()
        and not proyecto.solicitudes_cambio_tutor.filter(
            estado=EstadoSolicitudCambioTutor.PENDIENTE
        ).exists()
    )


@transaction.atomic
def solicitar_cambio_tutor(proyecto, tutor_propuesto, motivo, actor, request=None):
    proyecto = ProyectoTitulacion.objects.select_for_update().select_related(
        "maestrante__programa"
    ).get(pk=proyecto.pk)
    if not puede_solicitar_cambio_tutor(actor, proyecto):
        raise PermissionDenied("No puede solicitar un cambio de tutor.")
    asignacion = proyecto.asignaciones_tutor.select_for_update().get(
        estado=EstadoAsignacion.ACTIVO
    )
    if asignacion.tutor_id == tutor_propuesto.pk:
        raise ValidationError("Seleccione un tutor diferente al actual.")
    _validar_tutor_elegible(proyecto, tutor_propuesto)
    solicitud = SolicitudCambioTutor.objects.create(
        proyecto=proyecto,
        asignacion_actual=asignacion,
        tutor_propuesto=tutor_propuesto,
        motivo=str(motivo).strip(),
        solicitado_por=actor,
    )
    registrar_solicitud_aprobacion(
        proyecto=proyecto,
        tipo="cambio_tutor",
        tabla="solicitudes_cambio_tutor",
        registro_id=solicitud.pk,
    )
    if request:
        registrar_evento(
            request,
            accion="solicitar_cambio_tutor",
            tabla="solicitudes_cambio_tutor",
            registro_id=solicitud.pk,
            descripcion="Se solicitó un cambio de tutor.",
        )
    return solicitud


@transaction.atomic
def resolver_cambio_tutor(solicitud, actor, aprobar, observaciones=None, request=None):
    solicitud = SolicitudCambioTutor.objects.select_for_update().select_related(
        "proyecto__maestrante__programa",
        "asignacion_actual",
        "tutor_propuesto__usuario",
    ).get(pk=solicitud.pk)
    Tutor.objects.select_for_update().filter(
        pk=solicitud.tutor_propuesto_id
    ).exists()
    if (
        rol_usuario(actor) != "coordinador"
        or not usuario_tiene_permiso(actor, "CAMBIO_TUTOR_GESTIONAR")
        or not proyectos_visibles(actor).filter(pk=solicitud.proyecto_id).exists()
    ):
        raise PermissionDenied("No puede resolver este cambio de tutor.")
    if solicitud.estado != EstadoSolicitudCambioTutor.PENDIENTE:
        raise ValidationError("La solicitud ya fue resuelta.")
    observaciones = str(observaciones or "").strip() or None
    if not aprobar and not observaciones:
        raise ValidationError("Explique el motivo del rechazo.")
    if aprobar:
        asignacion_actual = AsignacionTutor.objects.select_for_update().get(
            pk=solicitud.asignacion_actual_id
        )
        if asignacion_actual.estado != EstadoAsignacion.ACTIVO:
            raise ValidationError("La asignación original ya no está activa.")
        _validar_tutor_elegible(solicitud.proyecto, solicitud.tutor_propuesto)
        asignacion_actual.estado = EstadoAsignacion.REEMPLAZADO
        asignacion_actual.motivo_cambio = solicitud.motivo
        asignacion_actual.save()
        nueva_asignacion = AsignacionTutor.objects.create(
            proyecto=solicitud.proyecto,
            tutor=solicitud.tutor_propuesto,
            asignado_por=actor,
            motivo_cambio=solicitud.motivo,
        )
        sesiones_actualizadas = solicitud.proyecto.tutorias.filter(
            fecha__gte=timezone.localdate(),
            estado__in=[EstadoTutoria.PROGRAMADA, EstadoTutoria.REPROGRAMADA],
        ).update(tutor=solicitud.tutor_propuesto)
        solicitud.estado = EstadoSolicitudCambioTutor.APROBADA
    else:
        nueva_asignacion = None
        sesiones_actualizadas = 0
        solicitud.estado = EstadoSolicitudCambioTutor.RECHAZADA
    solicitud.resuelto_por = actor
    solicitud.observaciones_resolucion = observaciones
    solicitud.fecha_resolucion = timezone.now()
    solicitud.save()
    _resolver_aprobacion(
        proyecto=solicitud.proyecto,
        tipo="cambio_tutor",
        tabla="solicitudes_cambio_tutor",
        registro_id=solicitud.pk,
        actor=actor,
        estado=EstadoAprobacion.APROBADO if aprobar else EstadoAprobacion.RECHAZADO,
        observaciones=observaciones,
    )
    if request:
        registrar_evento(
            request,
            accion="resolver_cambio_tutor",
            tabla="solicitudes_cambio_tutor",
            registro_id=solicitud.pk,
            descripcion=(
                f"Cambio de tutor {solicitud.estado}; "
                f"{sesiones_actualizadas} tutorías futuras actualizadas."
            ),
        )
    return nueva_asignacion


def validar_horario_tutoria(
    proyecto,
    tutor,
    fecha,
    hora_inicio,
    hora_fin,
    excluir_tutoria_id=None,
):
    if fecha < timezone.localdate():
        raise ValidationError("La fecha no puede estar en el pasado.")
    if hora_fin <= hora_inicio:
        raise ValidationError("La hora de fin debe ser posterior a la de inicio.")
    disponible = DisponibilidadTutor.objects.filter(
        tutor=tutor,
        esta_activa=True,
        dia_semana=fecha.weekday(),
        hora_inicio__lte=hora_inicio,
        hora_fin__gte=hora_fin,
    ).exists()
    if not disponible:
        raise ValidationError("El horario está fuera de la disponibilidad del tutor.")
    estados_ocupados = [
        EstadoTutoria.PROGRAMADA,
        EstadoTutoria.REPROGRAMADA,
        EstadoTutoria.REALIZADA,
    ]
    cruces_tutor = Tutoria.objects.filter(
        tutor=tutor,
        fecha=fecha,
        estado__in=estados_ocupados,
        hora_inicio__lt=hora_fin,
        hora_fin__gt=hora_inicio,
    )
    cruces_maestrante = Tutoria.objects.filter(
        proyecto__maestrante_id=proyecto.maestrante_id,
        fecha=fecha,
        estado__in=estados_ocupados,
        hora_inicio__lt=hora_fin,
        hora_fin__gt=hora_inicio,
    )
    if excluir_tutoria_id:
        cruces_tutor = cruces_tutor.exclude(pk=excluir_tutoria_id)
        cruces_maestrante = cruces_maestrante.exclude(pk=excluir_tutoria_id)
    if cruces_tutor.exists():
        raise ValidationError("El tutor ya tiene otra tutoría en ese horario.")
    if cruces_maestrante.exists():
        raise ValidationError("El maestrante ya tiene otra tutoría en ese horario.")


@transaction.atomic
def programar_tutoria(proyecto, tutor, datos, actor, request=None):
    proyecto = ProyectoTitulacion.objects.select_for_update().select_related(
        "maestrante__programa"
    ).get(pk=proyecto.pk)
    Tutor.objects.select_for_update().filter(pk=tutor.pk).exists()
    if not puede_gestionar_programacion(actor, proyecto):
        raise PermissionDenied("No puede programar tutorías para este proyecto.")
    asignacion = proyecto.asignaciones_tutor.filter(
        tutor=tutor,
        estado=EstadoAsignacion.ACTIVO,
    ).first()
    if asignacion is None:
        raise ValidationError("El tutor ya no es la asignación activa del proyecto.")
    limite = 9 if tiene_autorizacion_novena_tutoria(proyecto) else 8
    if proyecto.tutorias.count() >= limite:
        raise ValidationError(
            f"El proyecto ya tiene las {limite} tutorías permitidas "
            f"{'(incluida la novena excepcional)' if limite == 9 else ''}."
        )
    numero = int(datos["numero_tutoria"])
    if numero == 9 and not tiene_autorizacion_novena_tutoria(proyecto):
        raise ValidationError(
            "La novena tutoría requiere autorización previa de coordinación "
            "(AutorizacionNovenaTutoria)."
        )
    if proyecto.tutorias.filter(numero_tutoria=numero).exists():
        raise ValidationError(f"La tutoría {numero} ya está programada.")
    validar_horario_tutoria(
        proyecto,
        tutor,
        datos["fecha"],
        datos["hora_inicio"],
        datos["hora_fin"],
    )
    tutoria = Tutoria(
        proyecto=proyecto,
        tutor=tutor,
        numero_tutoria=numero,
        fecha=datos["fecha"],
        hora_inicio=datos["hora_inicio"],
        hora_fin=datos["hora_fin"],
        enlace_virtual=datos["enlace_virtual"],
        programada_por=actor,
    )
    tutoria.full_clean()
    tutoria.save()
    if request:
        registrar_evento(
            request,
            accion="programar_tutoria",
            tabla="tutorias",
            registro_id=tutoria.pk,
            descripcion=f"Se programó la tutoría {numero}.",
        )
    return tutoria


@transaction.atomic
def solicitar_reprogramacion(tutoria, datos, actor, request=None):
    tutoria = Tutoria.objects.select_for_update().select_related(
        "proyecto__maestrante", "tutor"
    ).get(pk=tutoria.pk)
    rol = rol_usuario(actor)
    permiso = (
        usuario_tiene_permiso(actor, "REPROGRAMACION_GESTIONAR")
        if rol == "coordinador"
        else usuario_tiene_permiso(actor, "REPROGRAMACION_SOLICITAR")
    )
    if (
        rol not in {"maestrante", "tutor", "coordinador"}
        or not permiso
        or not proyectos_visibles(actor).filter(pk=tutoria.proyecto_id).exists()
    ):
        raise PermissionDenied("No puede solicitar esta reprogramación.")
    if tutoria.estado in {EstadoTutoria.REALIZADA, EstadoTutoria.CANCELADA}:
        raise ValidationError("Esta tutoría ya no puede reprogramarse.")
    if tutoria.reprogramaciones.filter(estado=EstadoReprogramacion.PENDIENTE).exists():
        raise ValidationError("Ya existe una reprogramación pendiente.")
    validar_horario_tutoria(
        tutoria.proyecto,
        tutoria.tutor,
        datos["fecha_nueva"],
        datos["hora_inicio_nueva"],
        datos["hora_fin_nueva"],
        excluir_tutoria_id=tutoria.pk,
    )
    reprogramacion = ReprogramacionTutoria.objects.create(
        tutoria=tutoria,
        fecha_anterior=tutoria.fecha,
        hora_inicio_anterior=tutoria.hora_inicio,
        hora_fin_anterior=tutoria.hora_fin,
        fecha_nueva=datos["fecha_nueva"],
        hora_inicio_nueva=datos["hora_inicio_nueva"],
        hora_fin_nueva=datos["hora_fin_nueva"],
        motivo=datos["motivo"],
        solicitado_por=actor,
    )
    registrar_solicitud_aprobacion(
        proyecto=tutoria.proyecto,
        tipo="reprogramacion",
        tabla="reprogramaciones_tutoria",
        registro_id=reprogramacion.pk,
    )
    if request:
        registrar_evento(
            request,
            accion="solicitar_reprogramacion",
            tabla="reprogramaciones_tutoria",
            registro_id=reprogramacion.pk,
            descripcion="Se solicitó reprogramar una tutoría.",
        )
    return reprogramacion


@transaction.atomic
def resolver_reprogramacion(
    reprogramacion,
    actor,
    aprobar,
    request=None,
    observaciones=None,
):
    reprogramacion = ReprogramacionTutoria.objects.select_for_update().select_related(
        "tutoria__proyecto__maestrante", "tutoria__tutor"
    ).get(pk=reprogramacion.pk)
    Tutor.objects.select_for_update().filter(
        pk=reprogramacion.tutoria.tutor_id
    ).exists()
    if rol_usuario(actor) != "coordinador" or not proyectos_visibles(actor).filter(pk=reprogramacion.tutoria.proyecto_id).exists():
        raise PermissionDenied("No puede resolver esta reprogramación.")
    if reprogramacion.estado != EstadoReprogramacion.PENDIENTE:
        raise ValidationError("La solicitud ya fue resuelta.")
    observaciones = str(observaciones or "").strip() or None
    if not aprobar and not observaciones:
        raise ValidationError("Explique el motivo del rechazo.")
    if aprobar:
        validar_horario_tutoria(
            reprogramacion.tutoria.proyecto,
            reprogramacion.tutoria.tutor,
            reprogramacion.fecha_nueva,
            reprogramacion.hora_inicio_nueva,
            reprogramacion.hora_fin_nueva,
            excluir_tutoria_id=reprogramacion.tutoria_id,
        )
    reprogramacion.estado = EstadoReprogramacion.APROBADA if aprobar else EstadoReprogramacion.RECHAZADA
    reprogramacion.aprobado_por = actor
    reprogramacion.observaciones_resolucion = observaciones
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
        observaciones=observaciones,
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
def resolver_cambio_modalidad(
    solicitud: SolicitudCambioModalidad,
    actor,
    aprobar,
    observaciones=None,
    request=None,
):
    if not puede_revisar_cambio_modalidad(actor, solicitud.proyecto):
        raise PermissionDenied("No puede resolver esta solicitud.")
    if solicitud.estado != EstadoCambioModalidad.PENDIENTE:
        raise ValidationError("La solicitud ya fue resuelta.")
    if aprobar and not modalidad_disponible(
        solicitud.proyecto.maestrante.programa,
        solicitud.modalidad_propuesta,
    ):
        raise ValidationError("La modalidad propuesta ya no está disponible.")
    observaciones = str(observaciones or "").strip() or None
    if not aprobar and not observaciones:
        raise ValidationError("Debe explicar el motivo del rechazo.")

    solicitud.estado = (
        EstadoCambioModalidad.APROBADA
        if aprobar
        else EstadoCambioModalidad.RECHAZADA
    )
    solicitud.resuelto_por = actor
    solicitud.observaciones_resolucion = observaciones
    solicitud.fecha_resolucion = timezone.now()
    solicitud.save()

    if aprobar:
        proyecto = solicitud.proyecto
        proyecto.modalidad = solicitud.modalidad_propuesta
        proyecto.actualizado_por = actor
        proyecto.save(update_fields=("modalidad", "actualizado_por", "fecha_actualizacion"))
        if proyecto.modalidad != ModalidadProyecto.ARTICULO:
            proyecto.articulos.filter(esta_activo=True).update(
                esta_activo=False,
                fecha_actualizacion=timezone.now(),
            )

    aprobacion = _resolver_aprobacion(
        proyecto=solicitud.proyecto,
        tipo="cambio_modalidad",
        tabla="solicitudes_cambio_modalidad",
        registro_id=solicitud.pk,
        actor=actor,
        estado=(
            EstadoAprobacion.APROBADO if aprobar else EstadoAprobacion.RECHAZADO
        ),
        observaciones=observaciones,
    )
    if request:
        registrar_evento(
            request,
            accion="resolver_cambio_modalidad",
            tabla="solicitudes_cambio_modalidad",
            registro_id=solicitud.pk,
            descripcion=f"Solicitud de cambio de modalidad {solicitud.estado}.",
        )
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


# ---------------------------------------------------------------------------
# Fase 7A — Onboarding obligatorio del maestrante
# ---------------------------------------------------------------------------

MODULO_MINIMO_ONBOARDING = 5


def maestrante_es_elegible_onboarding(maestrante) -> bool:
    """Elegibilidad real vía Maestrante.modulo_actual (>= módulo 5)."""
    if not maestrante:
        return False
    return (maestrante.modulo_actual or 0) >= MODULO_MINIMO_ONBOARDING


def obtener_onboarding_maestrante(maestrante):
    if not maestrante:
        return None
    return OnboardingMaestrante.objects.filter(maestrante=maestrante).first()


def onboarding_completado(usuario) -> bool:
    """True si el usuario no es maestrante (no aplica el gate) o si ya completó."""
    if rol_usuario(usuario) != "maestrante":
        return True
    maestrante = getattr(usuario, "perfil_maestrante", None)
    onboarding = obtener_onboarding_maestrante(maestrante)
    return bool(onboarding and onboarding.estado == EstadoOnboarding.COMPLETADO)


@transaction.atomic
def iniciar_onboarding(usuario):
    """Crea (si no existe) el proyecto borrador + OnboardingMaestrante."""
    maestrante = getattr(usuario, "perfil_maestrante", None)
    if not maestrante:
        raise PermissionDenied("Solo un maestrante puede iniciar el onboarding.")
    if not maestrante_es_elegible_onboarding(maestrante):
        raise PermissionDenied(
            f"El maestrante debe estar al menos en el módulo {MODULO_MINIMO_ONBOARDING} "
            "para iniciar el onboarding."
        )
    onboarding = obtener_onboarding_maestrante(maestrante)
    if onboarding:
        return onboarding
    proyecto = ProyectoTitulacion.objects.filter(maestrante=maestrante).first()
    if proyecto is None:
        proyecto = ProyectoTitulacion.objects.create(
            maestrante=maestrante,
            tema="Tema pendiente de definición",
            modalidad=ModalidadProyecto.OTRA,
            estado=EstadoProyecto.BORRADOR,
            creado_por=usuario,
            actualizado_por=usuario,
        )
    onboarding = OnboardingMaestrante.objects.create(
        proyecto=proyecto,
        maestrante=maestrante,
        estado=EstadoOnboarding.EN_SELECCION,
    )
    return onboarding


@transaction.atomic
def completar_onboarding(usuario, modalidad):
    maestrante = getattr(usuario, "perfil_maestrante", None)
    onboarding = obtener_onboarding_maestrante(maestrante)
    if not onboarding:
        raise ValidationError("Debe iniciar el onboarding antes de seleccionar modalidad.")
    if onboarding.estado == EstadoOnboarding.COMPLETADO:
        raise ValidationError("El onboarding ya fue completado.")
    if not modalidad_disponible(maestrante.programa, modalidad):
        raise ValidationError("La modalidad seleccionada no está disponible para su programa.")
    onboarding.modalidad_seleccionada = modalidad
    onboarding.fecha_seleccion = timezone.now()
    onboarding.seleccionado_por = usuario
    onboarding.estado = EstadoOnboarding.COMPLETADO
    onboarding.full_clean()
    onboarding.save()
    proyecto = onboarding.proyecto
    proyecto.modalidad = modalidad
    proyecto.actualizado_por = usuario
    proyecto.save(update_fields=("modalidad", "actualizado_por", "fecha_actualizacion"))
    return onboarding


# ---------------------------------------------------------------------------
# Fase 7B — Modalidades configurables por el supervisor
# ---------------------------------------------------------------------------


def modalidades_configuradas_activas(programa=None):
    consulta = ModalidadConfigurada.objects.filter(esta_activa=True)
    if programa is not None:
        consulta = consulta.filter(Q(programa__isnull=True) | Q(programa=programa))
    else:
        consulta = consulta.filter(programa__isnull=True)
    return consulta.order_by("tipo_modalidad")


def etapas_de_modalidad(modalidad_configurada):
    return EtapaProducto.objects.filter(
        modalidad=modalidad_configurada, esta_activa=True
    ).order_by("orden")


# ---------------------------------------------------------------------------
# Fase 7C — Novena tutoría excepcional
# ---------------------------------------------------------------------------


def tiene_autorizacion_novena_tutoria(proyecto) -> bool:
    if not proyecto:
        return False
    return AutorizacionNovenaTutoria.objects.filter(proyecto=proyecto).exists()


def puede_autorizar_novena_tutoria(usuario) -> bool:
    return rol_usuario(usuario) == "coordinador" or usuario_tiene_permiso(
        usuario, "NOVENA_TUTORIA_AUTORIZAR"
    )


@transaction.atomic
def autorizar_novena_tutoria(proyecto, motivo, actor, request=None):
    if not puede_autorizar_novena_tutoria(actor):
        raise PermissionDenied("No puede autorizar una novena tutoría.")
    if tiene_autorizacion_novena_tutoria(proyecto):
        raise ValidationError("El proyecto ya tiene una novena tutoría autorizada.")
    if proyecto.tutorias.count() < 8:
        raise ValidationError(
            "Solo puede autorizarse la novena tutoría luego de completar las ocho ordinarias."
        )
    autorizacion = AutorizacionNovenaTutoria(
        proyecto=proyecto,
        solicitante=actor,
        motivo=motivo,
        autorizado_por=actor,
    )
    autorizacion.full_clean()
    autorizacion.save()
    if request:
        registrar_evento(
            request,
            accion="autorizar_novena_tutoria",
            tabla="autorizaciones_novena_tutoria",
            registro_id=autorizacion.pk,
            descripcion="Se autorizó una novena tutoría excepcional.",
        )
    return autorizacion


# ---------------------------------------------------------------------------
# Fase 7D — Entregas por etapa
# ---------------------------------------------------------------------------


def etapa_esta_bloqueada(proyecto, etapa) -> bool:
    """Refleja en UI el mismo bloqueo de orden que impone el trigger SQL
    `fase7_validar_orden_etapas`: una etapa obligatoria está bloqueada si
    alguna etapa obligatoria previa (mismo orden anterior) no tiene aún una
    entrega aprobada."""
    if not etapa.es_obligatoria:
        return False
    previas = EtapaProducto.objects.filter(
        modalidad=etapa.modalidad,
        es_obligatoria=True,
        orden__lt=etapa.orden,
    )
    for previa in previas:
        aprobada = EntregaEtapa.objects.filter(
            proyecto=proyecto, etapa=previa, estado=EstadoEtapaProducto.APROBADA
        ).exists()
        if not aprobada:
            return True
    return False


def puede_subir_entrega_etapa(usuario, proyecto) -> bool:
    return (
        rol_usuario(usuario) == "maestrante"
        and getattr(usuario, "perfil_maestrante", None) is not None
        and proyecto.maestrante_id == usuario.perfil_maestrante.id
    )


def puede_evaluar_entrega_etapa(usuario) -> bool:
    return rol_usuario(usuario) == "coordinador"


@transaction.atomic
def crear_entrega_etapa(proyecto, etapa, actor, *, archivo=None, comentario=None, request=None):
    if not puede_subir_entrega_etapa(actor, proyecto):
        raise PermissionDenied("Solo el maestrante propietario puede subir esta entrega.")
    if etapa_esta_bloqueada(proyecto, etapa):
        raise ValidationError(
            "Esta etapa está bloqueada hasta que las etapas obligatorias previas sean aprobadas."
        )
    ultima_version = EntregaEtapa.objects.filter(
        proyecto=proyecto, etapa=etapa
    ).order_by("-numero_version").first()
    numero_version = (ultima_version.numero_version + 1) if ultima_version else 1
    entrega = EntregaEtapa(
        proyecto=proyecto,
        etapa=etapa,
        numero_version=numero_version,
        archivo=archivo,
        comentario_maestrante=comentario,
        estado=EstadoEtapaProducto.ENVIADA,
    )
    entrega.full_clean()
    entrega.save()
    if request:
        registrar_evento(
            request,
            accion="crear_entrega_etapa",
            tabla="entregas_etapa",
            registro_id=entrega.pk,
            descripcion=f"Entrega v{numero_version} para etapa {etapa.nombre}.",
        )
    return entrega


@transaction.atomic
def evaluar_entrega_etapa(entrega, actor, estado, *, evaluacion=None, observaciones=None, request=None):
    if not puede_evaluar_entrega_etapa(actor):
        raise PermissionDenied("Solo coordinación puede evaluar entregas de etapa.")
    if estado not in {
        EstadoEtapaProducto.APROBADA,
        EstadoEtapaProducto.OBSERVADA,
        EstadoEtapaProducto.RECHAZADA,
    }:
        raise ValidationError("Estado de evaluación no permitido.")
    if entrega.estado == EstadoEtapaProducto.APROBADA:
        raise ValidationError("La entrega ya fue aprobada y es inmutable.")
    entrega.estado = estado
    entrega.evaluacion = evaluacion
    entrega.observaciones = observaciones
    entrega.coordinador_responsable = actor
    entrega.fecha_evaluacion = timezone.now()
    entrega.full_clean()
    entrega.save()
    if request:
        registrar_evento(
            request,
            accion="evaluar_entrega_etapa",
            tabla="entregas_etapa",
            registro_id=entrega.pk,
            descripcion=f"Entrega marcada como {estado}.",
        )
    return entrega


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
