"""Consultas y reglas de negocio del seguimiento académico."""

from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, OuterRef, Subquery
from django.utils import timezone

from apps.accounts.models import Maestrante, UsuarioCPOS
from apps.accounts.services import (
    registrar_bitacora as registrar_bitacora_accounts,
    usuario_tiene_permiso,
    verificar_usuario_activo,
)
from apps.titulacion.models import (
    Aprobacion,
    Articulo,
    ArchivoProyecto,
    AsignacionTutor,
    AsistenciaTutoria,
    AsistenciaTutoriaHistorial,
    EstadoAsignacion,
    EstadoProyecto,
    EstadoTutoria,
    Grabacion,
    ModalidadProyecto,
    ProyectoTitulacion,
    Tutoria,
)
from apps.titulacion.modalidades import obtener_regla_modalidad
from apps.titulacion.services import proyectos_visibles

from .models import Evidencia, EvidenciaVersion, Notificacion, ValidacionEvidencia


TOTAL_TUTORIAS_REQUERIDAS = 8
TOTAL_EVIDENCIAS_REQUERIDAS = 8
SECCIONES_ARTICULO = (
    "titulo",
    "introduccion",
    "metodologia",
    "resultados",
    "conclusiones",
    "referencias",
)


def calcular_porcentaje(cantidad, total):
    if not total:
        return 0
    return min(round((cantidad / total) * 100), 100)


def obtener_usuario_sistema(usuario):
    """Devuelve el usuario institucional autenticado sin crear un modelo paralelo."""
    if isinstance(usuario, UsuarioCPOS) and verificar_usuario_activo(usuario):
        return usuario
    return None


def obtener_nombre_rol(usuario):
    usuario_sistema = obtener_usuario_sistema(usuario)
    if not usuario_sistema:
        return ""
    return str(usuario_sistema.rol.nombre or "").strip().lower()


def es_maestrante(usuario):
    return obtener_nombre_rol(usuario) == "maestrante"


def es_tutor(usuario):
    return obtener_nombre_rol(usuario) == "tutor"


def es_coordinador(usuario):
    return obtener_nombre_rol(usuario) == "coordinador"


def es_supervisor(usuario):
    return obtener_nombre_rol(usuario) == "supervisor"


def es_rol_consulta_general(usuario):
    return es_coordinador(usuario) or es_supervisor(usuario)


def registrar_bitacora(
    usuario,
    accion,
    descripcion="",
    tabla_afectada="",
    registro_id=None,
    request=None,
):
    usuario_sistema = obtener_usuario_sistema(usuario)
    return registrar_bitacora_accounts(
        usuario=usuario_sistema,
        modulo="seguimiento",
        accion=accion,
        descripcion=descripcion,
        tabla_afectada=tabla_afectada or None,
        registro_id=registro_id,
        request=request,
    )


def _fin_tutoria(tutoria):
    fin = datetime.combine(tutoria.fecha, tutoria.hora_fin)
    if timezone.is_naive(fin):
        fin = timezone.make_aware(fin, timezone.get_current_timezone())
    return fin


def tutoria_ya_finalizo(tutoria):
    return bool(tutoria and _fin_tutoria(tutoria) <= timezone.now())


def asistencia_es_completa(asistencia):
    return bool(
        asistencia
        and asistencia.asistio_tutor
        and asistencia.asistio_maestrante
    )


def usuario_puede_registrar_asistencia(usuario, tutoria):
    return (
        tutoria
        and es_tutor(usuario)
        and tutoria.tutor.usuario_id == usuario.pk
        and usuario_tiene_permiso(usuario, "ASISTENCIA_REGISTRAR")
    )


def usuario_puede_corregir_asistencia(usuario, tutoria):
    return (
        tutoria
        and es_coordinador(usuario)
        and usuario_puede_ver_proyecto(usuario, tutoria.proyecto)
        and usuario_tiene_permiso(usuario, "ASISTENCIA_CORREGIR")
    )


def usuario_puede_gestionar_grabacion(usuario, tutoria, reemplazo=False):
    permiso = "GRABACION_REEMPLAZAR" if reemplazo else "GRABACION_REGISTRAR"
    return (
        tutoria
        and es_tutor(usuario)
        and tutoria.tutor.usuario_id == usuario.pk
        and usuario_tiene_permiso(usuario, permiso)
    )


def obtener_estado_integridad_tutoria(tutoria):
    asistencia = AsistenciaTutoria.objects.filter(tutoria=tutoria).first()
    evidencia = Evidencia.objects.filter(tutoria=tutoria).first()
    grabacion = Grabacion.objects.filter(tutoria=tutoria, esta_activa=True).first()
    asistencia_completa = asistencia_es_completa(asistencia)
    realizada_valida = (
        tutoria.estado == EstadoTutoria.REALIZADA and asistencia_completa
    )
    evidencia_validada = bool(evidencia and evidencia.estado == "validada")
    return {
        "asistencia": asistencia,
        "asistencia_completa": asistencia_completa,
        "realizada_valida": realizada_valida,
        "grabacion": grabacion,
        "tiene_grabacion": grabacion is not None,
        "evidencia": evidencia,
        "evidencia_validada": evidencia_validada,
        "completa": realizada_valida and evidencia_validada,
        "bloqueada": tutoria.estado in {
            EstadoTutoria.NO_REALIZADA,
            EstadoTutoria.CANCELADA,
        },
    }


@transaction.atomic
def registrar_o_corregir_asistencia(
    tutoria,
    *,
    actor,
    asistio_tutor,
    asistio_maestrante,
    estado_tutoria,
    observaciones=None,
    motivo_correccion=None,
    request=None,
):
    tutoria = (
        Tutoria.objects.select_for_update()
        .select_related("proyecto__maestrante__programa", "tutor__usuario")
        .get(pk=tutoria.pk)
    )
    asistencia = (
        AsistenciaTutoria.objects.select_for_update()
        .filter(tutoria=tutoria)
        .first()
    )
    es_correccion = asistencia is not None
    if es_correccion:
        if not usuario_puede_corregir_asistencia(actor, tutoria):
            raise PermissionDenied(
                "Solo coordinacion puede corregir una asistencia registrada."
            )
        if not str(motivo_correccion or "").strip():
            raise ValidationError("Debe justificar la correccion de asistencia.")
    elif not usuario_puede_registrar_asistencia(actor, tutoria):
        if not (
            estado_tutoria == EstadoTutoria.CANCELADA
            and usuario_puede_corregir_asistencia(actor, tutoria)
        ):
            raise PermissionDenied(
                "Solo el tutor asignado registra asistencia; coordinacion puede cancelar."
            )

    estados_finales = {
        EstadoTutoria.REALIZADA,
        EstadoTutoria.NO_REALIZADA,
        EstadoTutoria.CANCELADA,
    }
    if estado_tutoria not in estados_finales:
        raise ValidationError("Seleccione un estado final valido para la sesion.")
    if tutoria.estado == EstadoTutoria.CANCELADA and estado_tutoria != tutoria.estado:
        raise ValidationError("Una tutoria cancelada es un estado terminal.")
    if estado_tutoria in {EstadoTutoria.REALIZADA, EstadoTutoria.NO_REALIZADA}:
        if not tutoria_ya_finalizo(tutoria):
            raise ValidationError("No puede cerrar una tutoria que aun no ha finalizado.")
    if estado_tutoria == EstadoTutoria.REALIZADA and not (
        asistio_tutor and asistio_maestrante
    ):
        raise ValidationError(
            "Una tutoria realizada requiere asistencia del tutor y del maestrante."
        )
    if estado_tutoria == EstadoTutoria.NO_REALIZADA and (
        asistio_tutor and asistio_maestrante
    ):
        raise ValidationError(
            "Si ambos participantes asistieron, la sesion no puede quedar no realizada."
        )
    if estado_tutoria == EstadoTutoria.CANCELADA and not usuario_puede_corregir_asistencia(
        actor, tutoria
    ):
        raise PermissionDenied("Solo coordinacion puede cancelar una tutoria.")
    observaciones = str(observaciones or "").strip() or None
    if estado_tutoria in {EstadoTutoria.NO_REALIZADA, EstadoTutoria.CANCELADA} and not observaciones:
        raise ValidationError("Explique por que la sesion no se realizo.")
    if estado_tutoria in {EstadoTutoria.NO_REALIZADA, EstadoTutoria.CANCELADA} and (
        Evidencia.objects.filter(tutoria=tutoria).exists()
        or Grabacion.objects.filter(tutoria=tutoria, esta_activa=True).exists()
    ):
        raise ValidationError(
            "La sesion tiene evidencia o grabacion y no puede invalidarse."
        )

    valores_anteriores = None
    if asistencia:
        valores_anteriores = {
            "asistio_tutor": asistencia.asistio_tutor,
            "asistio_maestrante": asistencia.asistio_maestrante,
            "estado": tutoria.estado,
            "observaciones": asistencia.observaciones,
        }

    if tutoria.estado == EstadoTutoria.REALIZADA and estado_tutoria != EstadoTutoria.REALIZADA:
        tutoria.estado = estado_tutoria
        tutoria.observacion_general = observaciones
        tutoria.fecha_actualizacion = timezone.now()
        tutoria.save(update_fields=("estado", "observacion_general", "fecha_actualizacion"))

    if asistencia is None:
        asistencia = AsistenciaTutoria.objects.create(
            tutoria=tutoria,
            asistio_tutor=bool(asistio_tutor),
            asistio_maestrante=bool(asistio_maestrante),
            registrado_por=actor,
            observaciones=observaciones,
        )
    else:
        asistencia.asistio_tutor = bool(asistio_tutor)
        asistencia.asistio_maestrante = bool(asistio_maestrante)
        asistencia.registrado_por = actor
        asistencia.observaciones = observaciones
        asistencia.fecha_actualizacion = timezone.now()
        asistencia.save(
            update_fields=(
                "asistio_tutor",
                "asistio_maestrante",
                "registrado_por",
                "observaciones",
                "fecha_actualizacion",
            )
        )

    if tutoria.estado != estado_tutoria:
        tutoria.estado = estado_tutoria
        tutoria.observacion_general = observaciones
        tutoria.fecha_actualizacion = timezone.now()
        tutoria.save(update_fields=("estado", "observacion_general", "fecha_actualizacion"))

    if valores_anteriores:
        cambio = any(
            (
                valores_anteriores["asistio_tutor"] != bool(asistio_tutor),
                valores_anteriores["asistio_maestrante"] != bool(asistio_maestrante),
                valores_anteriores["estado"] != estado_tutoria,
                (valores_anteriores["observaciones"] or "") != (observaciones or ""),
            )
        )
        if not cambio:
            raise ValidationError("La correccion no contiene ningun cambio.")
        AsistenciaTutoriaHistorial.objects.create(
            asistencia=asistencia,
            tutoria=tutoria,
            asistio_tutor_anterior=valores_anteriores["asistio_tutor"],
            asistio_maestrante_anterior=valores_anteriores["asistio_maestrante"],
            estado_tutoria_anterior=valores_anteriores["estado"],
            asistio_tutor_nuevo=bool(asistio_tutor),
            asistio_maestrante_nuevo=bool(asistio_maestrante),
            estado_tutoria_nuevo=estado_tutoria,
            observaciones_anteriores=valores_anteriores["observaciones"],
            observaciones_nuevas=observaciones,
            motivo_correccion=str(motivo_correccion).strip(),
            corregido_por=actor,
        )

    registrar_bitacora(
        actor,
        accion=(
            "corregir_asistencia_tutoria"
            if es_correccion
            else (
                "cancelar_tutoria"
                if estado_tutoria == EstadoTutoria.CANCELADA
                else "registrar_asistencia_tutoria"
            )
        ),
        descripcion=f"Asistencia de la tutoria {tutoria.pk}: {estado_tutoria}.",
        tabla_afectada="asistencias_tutoria",
        registro_id=asistencia.pk,
        request=request,
    )
    return asistencia


@transaction.atomic
def crear_version_grabacion(tutoria, *, actor, datos, request=None):
    tutoria = (
        Tutoria.objects.select_for_update()
        .select_related("proyecto", "tutor__usuario")
        .get(pk=tutoria.pk)
    )
    estado = obtener_estado_integridad_tutoria(tutoria)
    if not estado["realizada_valida"]:
        raise ValidationError(
            "La grabacion solo puede registrarse para una tutoria realizada con asistencia completa."
        )
    activa = (
        Grabacion.objects.select_for_update()
        .filter(tutoria=tutoria, esta_activa=True)
        .first()
    )
    if not usuario_puede_gestionar_grabacion(actor, tutoria, reemplazo=bool(activa)):
        raise PermissionDenied(
            "Solo el tutor asignado puede registrar o reemplazar la grabacion."
        )
    numero = (
        Grabacion.objects.filter(tutoria=tutoria).aggregate(mayor=Max("numero_version"))["mayor"]
        or 0
    ) + 1
    if activa:
        activa.esta_activa = False
        activa.fecha_actualizacion = timezone.now()
        activa.save(update_fields=("esta_activa", "fecha_actualizacion"))
    grabacion = Grabacion.objects.create(
        tutoria=tutoria,
        tipo_grabacion=datos["tipo_grabacion"],
        enlace_grabacion=datos.get("enlace_grabacion") or None,
        ruta_archivo=datos.get("ruta_archivo") or None,
        nombre_original=datos.get("nombre_original") or None,
        extension=datos.get("extension") or None,
        tamano_bytes=datos.get("tamano_bytes") or None,
        numero_version=numero,
        esta_activa=True,
        reemplaza_grabacion=activa,
        registrado_por=actor,
    )
    registrar_bitacora(
        actor,
        accion=("reemplazar_grabacion" if activa else "registrar_grabacion"),
        descripcion=f"Grabacion v{numero} de la tutoria {tutoria.pk}.",
        tabla_afectada="grabaciones",
        registro_id=grabacion.pk,
        request=request,
    )
    return grabacion


def obtener_proyectos_del_usuario(usuario):
    usuario_sistema = obtener_usuario_sistema(usuario)
    if not usuario_sistema:
        return ProyectoTitulacion.objects.none()
    return proyectos_visibles(usuario_sistema)


def obtener_proyecto_del_usuario(usuario):
    return obtener_proyectos_del_usuario(usuario).first()


def usuario_puede_ver_proyecto(usuario, proyecto):
    if not proyecto:
        return False
    return obtener_proyectos_del_usuario(usuario).filter(pk=proyecto.pk).exists()


def obtener_tutorias_por_usuario(usuario):
    proyectos = obtener_proyectos_del_usuario(usuario)
    return (
        Tutoria.objects.select_related(
            "proyecto",
            "proyecto__maestrante__usuario",
            "tutor__usuario",
        )
        .filter(proyecto__in=proyectos)
        .order_by("fecha", "hora_inicio", "numero_tutoria")
    )


def calcular_progreso_tutorias(proyecto):
    if not proyecto:
        return {
            "total": 0,
            "programadas": 0,
            "realizadas": 0,
            "bloqueadas": 0,
            "pendientes": TOTAL_TUTORIAS_REQUERIDAS,
            "porcentaje": 0,
            "cumple": False,
        }
    tutorias = Tutoria.objects.filter(proyecto=proyecto)
    total = tutorias.count()
    realizadas = tutorias.filter(
        estado=EstadoTutoria.REALIZADA,
        asistencia__asistio_tutor=True,
        asistencia__asistio_maestrante=True,
    ).count()
    programadas = tutorias.filter(
        estado__in=(EstadoTutoria.PROGRAMADA, EstadoTutoria.REPROGRAMADA)
    ).count()
    bloqueadas = tutorias.filter(
        estado__in=(EstadoTutoria.NO_REALIZADA, EstadoTutoria.CANCELADA)
    ).count()
    return {
        "total": total,
        "programadas": programadas,
        "realizadas": realizadas,
        "bloqueadas": bloqueadas,
        "pendientes": max(TOTAL_TUTORIAS_REQUERIDAS - realizadas, 0),
        "porcentaje": calcular_porcentaje(realizadas, TOTAL_TUTORIAS_REQUERIDAS),
        "cumple": realizadas == TOTAL_TUTORIAS_REQUERIDAS,
    }


def obtener_tutorias_pendientes(usuario=None):
    consulta = (
        obtener_tutorias_por_usuario(usuario)
        if usuario
        else Tutoria.objects.select_related("proyecto", "tutor__usuario").all()
    )
    return consulta.exclude(estado=EstadoTutoria.REALIZADA).order_by(
        "fecha", "hora_inicio", "numero_tutoria"
    )


def obtener_asistencias_tutoria(tutoria):
    if not tutoria:
        return AsistenciaTutoria.objects.none()
    return AsistenciaTutoria.objects.filter(tutoria=tutoria).select_related(
        "registrado_por"
    )


def obtener_grabaciones_tutoria(tutoria):
    if not tutoria:
        return Grabacion.objects.none()
    return (
        Grabacion.objects.filter(tutoria=tutoria)
        .select_related("registrado_por", "reemplaza_grabacion")
        .order_by("-esta_activa", "-numero_version", "-fecha_creacion")
    )


def obtener_evidencias_por_usuario(usuario):
    proyectos = obtener_proyectos_del_usuario(usuario)
    return (
        Evidencia.objects.select_related(
            "proyecto",
            "tutoria",
            "subido_por",
        )
        .filter(proyecto__in=proyectos)
        .order_by("-fecha_creacion", "-id")
    )


def obtener_evidencias_por_tutoria(tutoria):
    if not tutoria:
        return Evidencia.objects.none()
    return Evidencia.objects.filter(tutoria=tutoria).select_related("subido_por")


def obtener_evidencias_observadas(proyecto=None):
    consulta = Evidencia.objects.filter(estado="observada").select_related(
        "proyecto", "tutoria", "subido_por"
    )
    if proyecto:
        consulta = consulta.filter(proyecto=proyecto)
    return consulta.order_by("-fecha_creacion", "-id")


def calcular_progreso_evidencias(proyecto):
    if not proyecto:
        return {
            "total": 0,
            "validadas": 0,
            "validadas_correspondientes": 0,
            "observadas": 0,
            "rechazadas": 0,
            "en_revision": 0,
            "pendientes": TOTAL_EVIDENCIAS_REQUERIDAS,
            "porcentaje": 0,
            "cumple": False,
        }
    evidencias = Evidencia.objects.filter(proyecto=proyecto)
    total = evidencias.count()
    validadas = evidencias.filter(estado="validada").count()
    validadas_correspondientes = evidencias.filter(
        estado="validada",
        tutoria__estado=EstadoTutoria.REALIZADA,
        tutoria__asistencia__asistio_tutor=True,
        tutoria__asistencia__asistio_maestrante=True,
    ).count()
    observadas = evidencias.filter(estado="observada").count()
    rechazadas = evidencias.filter(estado="rechazada").count()
    en_revision = evidencias.filter(
        estado__in=("pendiente", "cargada", "en_revision")
    ).count()
    return {
        "total": total,
        "validadas": validadas,
        "validadas_correspondientes": validadas_correspondientes,
        "observadas": observadas,
        "rechazadas": rechazadas,
        "en_revision": en_revision,
        "pendientes": max(
            TOTAL_EVIDENCIAS_REQUERIDAS - validadas_correspondientes,
            0,
        ),
        "porcentaje": calcular_porcentaje(
            validadas_correspondientes,
            TOTAL_EVIDENCIAS_REQUERIDAS,
        ),
        "cumple": validadas_correspondientes == TOTAL_EVIDENCIAS_REQUERIDAS,
    }


def obtener_resumen_evidencias_proyecto(proyecto):
    """Contrato consumido por Titulación para mostrar cifras reales."""
    progreso = calcular_progreso_evidencias(proyecto)
    return {
        "total": progreso["total"],
        "validadas": progreso["validadas"],
        "validadas_correspondientes": progreso["validadas_correspondientes"],
        "observadas": progreso["observadas"],
        "rechazadas": progreso["rechazadas"],
        "en_revision": progreso["en_revision"],
        "pendientes": progreso["pendientes"],
        "porcentaje": progreso["porcentaje"],
        "cumple": progreso["cumple"],
    }


def obtener_siguiente_numero_version(evidencia):
    ultima = EvidenciaVersion.objects.filter(evidencia=evidencia).aggregate(
        mayor=Max("numero_version")
    )["mayor"]
    return (ultima or 0) + 1


def obtener_historial_evidencia(evidencia):
    if not evidencia:
        return {
            "versiones": EvidenciaVersion.objects.none(),
            "validaciones": ValidacionEvidencia.objects.none(),
        }
    return {
        "versiones": EvidenciaVersion.objects.filter(evidencia=evidencia)
        .select_related("subido_por")
        .order_by("-numero_version", "-id"),
        "validaciones": ValidacionEvidencia.objects.filter(evidencia=evidencia)
        .select_related("validado_por", "evidencia_version")
        .order_by("-fecha_creacion", "-id"),
    }


def usuario_puede_subir_evidencia(usuario, tutoria=None):
    autorizado = es_maestrante(usuario) and usuario_tiene_permiso(
        usuario, "EVIDENCIA_SUBIR"
    )
    if autorizado and tutoria is not None:
        autorizado = (
            tutoria.proyecto.maestrante.usuario_id == usuario.pk
            and obtener_estado_integridad_tutoria(tutoria)["realizada_valida"]
        )
    return autorizado


def usuario_puede_validar_evidencia(usuario, evidencia=None):
    autorizado = es_tutor(usuario) and usuario_tiene_permiso(
        usuario, "EVIDENCIA_VALIDAR"
    )
    if autorizado and evidencia is not None:
        autorizado = (
            evidencia.tutoria.tutor.usuario_id == usuario.pk
            and usuario_puede_ver_proyecto(usuario, evidencia.proyecto)
        )
    return autorizado


def usuario_puede_editar_articulo(usuario, proyecto):
    return (
        es_maestrante(usuario)
        and proyecto.maestrante.usuario_id == usuario.pk
        and proyecto.modalidad == ModalidadProyecto.ARTICULO
        and usuario_tiene_permiso(usuario, "ARTICULO_EDITAR")
    )


def obtener_articulo_proyecto(proyecto):
    if not proyecto:
        return None
    return Articulo.objects.filter(proyecto=proyecto, esta_activo=True).first()


def calcular_avance_articulo(articulo):
    detalle = []
    completas = 0
    for seccion in SECCIONES_ARTICULO:
        contenido = getattr(articulo, seccion, None) if articulo else None
        completa = bool(contenido and str(contenido).strip())
        completas += int(completa)
        detalle.append(
            {"seccion": seccion, "completa": completa, "contenido": contenido}
        )
    return {
        "secciones_completas": completas,
        "total_secciones": len(SECCIONES_ARTICULO),
        "porcentaje": calcular_porcentaje(completas, len(SECCIONES_ARTICULO)),
        "detalle": detalle,
    }


def obtener_estado_producto_final(proyecto, regla=None):
    if not proyecto:
        return {"cumplido": False, "archivo": None, "detalle": "Sin proyecto"}
    regla = regla or obtener_regla_modalidad(
        proyecto.maestrante.programa,
        proyecto.modalidad,
    )
    if regla["requiere_articulo"]:
        articulo = obtener_articulo_proyecto(proyecto)
        avance = calcular_avance_articulo(articulo)
        completo = avance["porcentaje"] == 100
        enviado = bool(articulo and articulo.fecha_envio_revista)
        return {
            "cumplido": completo and enviado,
            "archivo": None,
            "detalle": (
                "Artículo completo y envío registrado"
                if completo and enviado
                else f'Artículo {avance["porcentaje"]}% · envío '
                f'{"registrado" if enviado else "pendiente"}'
            ),
            "avance_articulo": avance,
            "articulo": articulo,
        }

    archivos = ArchivoProyecto.objects.filter(
        proyecto=proyecto,
        tipo_archivo=regla["tipo_archivo_final"],
    )
    ultima_revision = Aprobacion.objects.filter(
        proyecto=proyecto,
        tipo_aprobacion="archivo_proyecto",
        referencia_tabla="archivos_proyecto",
        referencia_id=OuterRef("pk"),
    ).order_by("-fecha_creacion", "-id")
    archivo = (
        archivos.annotate(
            estado_revision=Subquery(ultima_revision.values("estado")[:1])
        )
        .filter(estado_revision="aprobado")
        .order_by("-fecha_creacion")
        .first()
    )
    return {
        "cumplido": archivo is not None,
        "archivo": archivo,
        "detalle": (
            f"Archivo aprobado: {archivo.nombre_original}"
            if archivo
            else "Pendiente de subir y aprobar el archivo final"
        ),
    }


def puede_cerrar_proceso(proyecto):
    if not proyecto:
        return False
    progreso_tutorias = calcular_progreso_tutorias(proyecto)
    progreso_evidencias = calcular_progreso_evidencias(proyecto)
    regla = obtener_regla_modalidad(
        proyecto.maestrante.programa,
        proyecto.modalidad,
    )
    producto_final = obtener_estado_producto_final(proyecto, regla)
    return all(
        (
            proyecto.estado in {EstadoProyecto.APROBADO, EstadoProyecto.CERRADO},
            AsignacionTutor.objects.filter(
                proyecto=proyecto,
                estado=EstadoAsignacion.ACTIVO,
            ).exists(),
            progreso_tutorias["cumple"],
            progreso_evidencias["cumple"],
            producto_final["cumplido"],
        )
    )


def obtener_checklist_cierre(proyecto):
    progreso_tutorias = calcular_progreso_tutorias(proyecto)
    progreso_evidencias = calcular_progreso_evidencias(proyecto)
    regla = obtener_regla_modalidad(
        proyecto.maestrante.programa,
        proyecto.modalidad,
    )
    producto_final = obtener_estado_producto_final(proyecto, regla)
    articulo = producto_final.get("articulo")
    avance_articulo = producto_final.get("avance_articulo", calcular_avance_articulo(None))
    asignacion_activa = AsignacionTutor.objects.filter(
        proyecto=proyecto,
        estado=EstadoAsignacion.ACTIVO,
    ).exists()
    tema_aprobado = proyecto.estado in {EstadoProyecto.APROBADO, EstadoProyecto.CERRADO}
    items = [
        {
            "codigo": "PRO-APR",
            "nombre": "Proyecto aprobado",
            "cumplido": tema_aprobado,
            "detalle": "Aprobado" if tema_aprobado else "Pendiente de aprobación",
        },
        {
            "codigo": "TUT-ASG",
            "nombre": "Tutor asignado",
            "cumplido": asignacion_activa,
            "detalle": "Asignación activa" if asignacion_activa else "Sin tutor activo",
        },
        {
            "codigo": "TUT-008",
            "nombre": "Ocho tutorías realizadas",
            "cumplido": progreso_tutorias["cumple"],
            "detalle": f'{progreso_tutorias["realizadas"]}/8 realizadas',
        },
        {
            "codigo": "EVI-008",
            "nombre": "Ocho evidencias validadas",
            "cumplido": progreso_evidencias["cumple"],
            "detalle": (
                f'{progreso_evidencias["validadas_correspondientes"]}/8 '
                "validadas y vinculadas a sesiones realizadas"
            ),
        },
    ]
    if regla["requiere_articulo"]:
        # Nota: el envío/publicación en revista es un trámite externo al CPOS
        # y ya NO bloquea el cierre del proceso (decisión de negocio Fase 7).
        # El registro de envío (registrar_envio_revista / EnvioRevistaForm)
        # se conserva como información opcional para el maestrante.
        items.append(
            {
                "codigo": "ART-100",
                "nombre": "Artículo por secciones",
                "cumplido": avance_articulo["porcentaje"] == 100,
                "detalle": f'{avance_articulo["porcentaje"]}% completo',
            }
        )
    else:
        items.append(
            {
                "codigo": "MOD-FIN",
                "nombre": regla["producto_final_nombre"],
                "cumplido": producto_final["cumplido"],
                "detalle": producto_final["detalle"],
            }
        )
    return {
        "proyecto": proyecto,
        "progreso_tutorias": progreso_tutorias,
        "progreso_evidencias": progreso_evidencias,
        "articulo": articulo,
        "avance_articulo": avance_articulo,
        "regla_modalidad": regla,
        "producto_final": producto_final,
        "items": items,
        "puede_cerrar": all(item["cumplido"] for item in items),
    }


def obtener_notificaciones_usuario(usuario, solo_no_leidas=False):
    usuario_sistema = obtener_usuario_sistema(usuario)
    if not usuario_sistema:
        return Notificacion.objects.none()
    consulta = Notificacion.objects.filter(usuario=usuario_sistema)
    if solo_no_leidas:
        consulta = consulta.filter(fecha_lectura__isnull=True)
    return consulta.order_by("-fecha_creacion", "-id")


def contar_notificaciones_no_leidas(usuario):
    return obtener_notificaciones_usuario(usuario, solo_no_leidas=True).count()


def obtener_dashboard_seguimiento(usuario):
    usuario_sistema = obtener_usuario_sistema(usuario)
    proyecto = obtener_proyecto_del_usuario(usuario_sistema)
    articulo = obtener_articulo_proyecto(proyecto)
    regla_modalidad = (
        obtener_regla_modalidad(proyecto.maestrante.programa, proyecto.modalidad)
        if proyecto
        else None
    )
    producto_final = (
        obtener_estado_producto_final(proyecto, regla_modalidad)
        if proyecto
        else None
    )
    return {
        "usuario_sistema": usuario_sistema,
        "rol": obtener_nombre_rol(usuario_sistema),
        "proyecto": proyecto,
        "progreso_tutorias": calcular_progreso_tutorias(proyecto),
        "progreso_evidencias": calcular_progreso_evidencias(proyecto),
        "articulo": articulo,
        "avance_articulo": calcular_avance_articulo(articulo),
        "regla_modalidad": regla_modalidad,
        "producto_final": producto_final,
        "puede_cerrar": puede_cerrar_proceso(proyecto),
        "tutorias_pendientes": obtener_tutorias_pendientes(usuario_sistema)[:5],
        "evidencias_observadas": obtener_evidencias_observadas(proyecto)[:5],
        "notificaciones": obtener_notificaciones_usuario(usuario_sistema)[:5],
        "notificaciones_no_leidas": contar_notificaciones_no_leidas(
            usuario_sistema
        ),
    }


def obtener_reportes_seguimiento(usuario):
    proyectos = obtener_proyectos_del_usuario(usuario)
    tutorias = Tutoria.objects.filter(proyecto__in=proyectos)
    evidencias = Evidencia.objects.filter(proyecto__in=proyectos)
    maestrantes = Maestrante.objects.filter(
        proyectos_titulacion__in=proyectos
    ).distinct()
    asignaciones = AsignacionTutor.objects.filter(proyecto__in=proyectos)

    avance_por_proyecto = [
        {
            "proyecto": proyecto,
            "progreso_tutorias": calcular_progreso_tutorias(proyecto),
            "progreso_evidencias": calcular_progreso_evidencias(proyecto),
            "puede_cerrar": puede_cerrar_proceso(proyecto),
        }
        for proyecto in proyectos.select_related("maestrante__usuario")[:20]
    ]
    return {
        "total_maestrantes": maestrantes.count(),
        "total_proyectos": proyectos.count(),
        "total_tutorias": tutorias.count(),
        "total_evidencias": evidencias.count(),
        "maestrantes_por_estado": maestrantes.values("estado_titulacion")
        .annotate(total=Count("id"))
        .order_by("estado_titulacion"),
        "tutorias_por_estado": tutorias.values("estado")
        .annotate(total=Count("id"))
        .order_by("estado"),
        "evidencias_por_estado": evidencias.values("estado")
        .annotate(total=Count("id"))
        .order_by("estado"),
        "proyectos_por_estado": proyectos.values("estado")
        .annotate(total=Count("id"))
        .order_by("estado"),
        "tutorias_pendientes": tutorias.exclude(estado=EstadoTutoria.REALIZADA)
        .select_related("proyecto", "tutor__usuario")
        .order_by("fecha", "hora_inicio")[:20],
        "evidencias_observadas": evidencias.filter(estado="observada")
        .select_related("proyecto", "tutoria", "subido_por")
        .order_by("-fecha_creacion")[:20],
        "tutores_asignados": asignaciones.select_related(
            "proyecto", "tutor__usuario"
        ).order_by("-fecha_asignacion", "-id")[:20],
        "avance_por_proyecto": avance_por_proyecto,
    }
