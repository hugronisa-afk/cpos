"""Consultas y reglas de negocio del seguimiento académico."""

from django.db.models import Count, Max, OuterRef, Subquery

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
            "realizadas": 0,
            "pendientes": TOTAL_TUTORIAS_REQUERIDAS,
            "porcentaje": 0,
            "cumple": False,
        }
    tutorias = Tutoria.objects.filter(proyecto=proyecto)
    total = tutorias.count()
    realizadas = tutorias.filter(estado=EstadoTutoria.REALIZADA).count()
    return {
        "total": total,
        "realizadas": realizadas,
        "pendientes": max(TOTAL_TUTORIAS_REQUERIDAS - realizadas, 0),
        "porcentaje": calcular_porcentaje(realizadas, TOTAL_TUTORIAS_REQUERIDAS),
        "cumple": realizadas >= TOTAL_TUTORIAS_REQUERIDAS,
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
    return Grabacion.objects.filter(tutoria=tutoria).select_related("registrado_por")


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
            "observadas": 0,
            "pendientes": TOTAL_EVIDENCIAS_REQUERIDAS,
            "porcentaje": 0,
            "cumple": False,
        }
    evidencias = Evidencia.objects.filter(proyecto=proyecto)
    total = evidencias.count()
    validadas = evidencias.filter(estado="validada").count()
    observadas = evidencias.filter(estado="observada").count()
    return {
        "total": total,
        "validadas": validadas,
        "observadas": observadas,
        "pendientes": max(TOTAL_EVIDENCIAS_REQUERIDAS - validadas, 0),
        "porcentaje": calcular_porcentaje(validadas, TOTAL_EVIDENCIAS_REQUERIDAS),
        "cumple": validadas >= TOTAL_EVIDENCIAS_REQUERIDAS,
    }


def obtener_resumen_evidencias_proyecto(proyecto):
    """Contrato consumido por Titulación para mostrar cifras reales."""
    progreso = calcular_progreso_evidencias(proyecto)
    return {
        "total": progreso["total"],
        "validadas": progreso["validadas"],
        "observadas": progreso["observadas"],
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
        .select_related("validado_por")
        .order_by("-fecha_creacion", "-id"),
    }


def usuario_puede_subir_evidencia(usuario):
    return es_maestrante(usuario) and usuario_tiene_permiso(usuario, "EVIDENCIA_SUBIR")


def usuario_puede_validar_evidencia(usuario):
    return es_tutor(usuario) and usuario_tiene_permiso(usuario, "EVIDENCIA_VALIDAR")


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
            "detalle": f'{progreso_evidencias["validadas"]}/8 validadas',
        },
    ]
    if regla["requiere_articulo"]:
        envio_revista = bool(articulo and articulo.fecha_envio_revista)
        items.extend(
            (
                {
                    "codigo": "ART-100",
                    "nombre": "Artículo por secciones",
                    "cumplido": avance_articulo["porcentaje"] == 100,
                    "detalle": f'{avance_articulo["porcentaje"]}% completo',
                },
                {
                    "codigo": "REV-ENV",
                    "nombre": "Envío del artículo a revista",
                    "cumplido": envio_revista,
                    "detalle": "Envío registrado" if envio_revista else "Pendiente de envío",
                },
            )
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
