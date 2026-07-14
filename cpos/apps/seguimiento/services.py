from django.db.models import Count, Q, Max
from django.utils import timezone

from .models import (
    Usuario,
    Maestrante,
    Tutor,
    ProyectoTitulacion,
    AsignacionTutor,
    Tutoria,
    AsistenciaTutoria,
    Grabacion,
    Evidencia,
    EvidenciaVersion,
    ValidacionEvidencia,
    Articulo,
    Notificacion,
    Bitacora,
)


# ============================================================
# CONSTANTES DEL MÓDULO
# ============================================================

TOTAL_TUTORIAS_REQUERIDAS = 8
TOTAL_EVIDENCIAS_REQUERIDAS = 8

SECCIONES_ARTICULO = [
    "titulo",
    "introduccion",
    "metodologia",
    "resultados",
    "conclusiones",
    "referencias",
]


# ============================================================
# UTILIDADES GENERALES
# ============================================================

def calcular_porcentaje(cantidad, total):
    """
    Calcula un porcentaje seguro.
    Evita errores por división entre cero.
    """
    if not total:
        return 0

    porcentaje = round((cantidad / total) * 100)

    if porcentaje > 100:
        return 100

    return porcentaje


def obtener_ip_request(request):
    """
    Obtiene la IP del usuario desde el request.
    Sirve para registrar bitácora.
    """
    if not request:
        return None

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def obtener_usuario_sistema(usuario):
    """
    Convierte el usuario autenticado de Django en el usuario de la tabla usuarios.

    Esto es útil porque el proyecto puede estar usando:
    - request.user de Django
    - o directamente la tabla usuarios creada en Supabase

    Si ya recibe un Usuario del modelo usuarios, lo devuelve igual.
    """

    if not usuario:
        return None

    if hasattr(usuario, "_meta") and usuario._meta.db_table == "usuarios":
        return usuario

    if hasattr(usuario, "is_authenticated") and not usuario.is_authenticated:
        return None

    email = getattr(usuario, "email", None)
    username = getattr(usuario, "username", None)

    filtros = Q()

    if email:
        filtros |= Q(email__iexact=email)

    if username:
        filtros |= Q(email__iexact=username)

    if filtros:
        return Usuario.objects.filter(filtros).first()

    return None


def obtener_nombre_rol(usuario):
    """
    Retorna el nombre del rol en minúsculas.
    """
    usuario_sistema = obtener_usuario_sistema(usuario)

    if not usuario_sistema:
        return ""

    if not usuario_sistema.rol:
        return ""

    return (usuario_sistema.rol.nombre or "").strip().lower()


def es_maestrante(usuario):
    rol = obtener_nombre_rol(usuario)
    return "maestrante" in rol or "estudiante" in rol


def es_tutor(usuario):
    rol = obtener_nombre_rol(usuario)
    return "tutor" in rol or "docente" in rol


def es_coordinador(usuario):
    rol = obtener_nombre_rol(usuario)
    return "coordinador" in rol


def es_supervisor(usuario):
    rol = obtener_nombre_rol(usuario)
    return "supervisor" in rol


def es_rol_consulta_general(usuario):
    """
    Roles que pueden ver información general.
    """
    return es_coordinador(usuario) or es_supervisor(usuario)


# ============================================================
# BITÁCORA
# ============================================================

def registrar_bitacora(
    usuario,
    accion,
    descripcion="",
    tabla_afectada="",
    registro_id=None,
    request=None,
):
    """
    Registra una acción importante en la bitácora.

    Esta función NO debe romper el sistema si la bitácora falla.
    Por eso usa try/except.
    """

    try:
        usuario_sistema = obtener_usuario_sistema(usuario)

        return Bitacora.objects.create(
            usuario=usuario_sistema,
            accion=accion,
            descripcion=descripcion,
            tabla_afectada=tabla_afectada,
            registro_id=registro_id,
            ip=obtener_ip_request(request),
            fecha=timezone.now(),
        )

    except Exception:
        return None


# ============================================================
# PROYECTOS SEGÚN USUARIO
# ============================================================

def obtener_proyectos_del_usuario(usuario):
    """
    Obtiene los proyectos visibles para un usuario según su rol.

    Maestrante:
        ve sus propios proyectos.

    Tutor:
        ve proyectos asignados.

    Coordinador / Supervisor:
        ven todos.
    """

    usuario_sistema = obtener_usuario_sistema(usuario)

    if not usuario_sistema:
        return ProyectoTitulacion.objects.none()

    queryset = ProyectoTitulacion.objects.select_related(
        "maestrante",
        "maestrante__usuario",
        "maestrante__programa",
        "maestrante__cohorte",
    ).all()

    if es_rol_consulta_general(usuario_sistema):
        return queryset.order_by("-id")

    if es_maestrante(usuario_sistema):
        return queryset.filter(
            maestrante__usuario=usuario_sistema
        ).order_by("-id")

    if es_tutor(usuario_sistema):
        tutor = Tutor.objects.filter(usuario=usuario_sistema).first()

        if not tutor:
            return ProyectoTitulacion.objects.none()

        proyectos_ids = AsignacionTutor.objects.filter(
            tutor=tutor
        ).values_list("proyecto_id", flat=True)

        return queryset.filter(id__in=proyectos_ids).order_by("-id")

    return ProyectoTitulacion.objects.none()


def obtener_proyecto_del_usuario(usuario):
    """
    Obtiene el proyecto principal del usuario.

    Se usa para dashboard o pantallas donde trabajamos con un solo proyecto.
    """
    return obtener_proyectos_del_usuario(usuario).first()


def usuario_puede_ver_proyecto(usuario, proyecto):
    """
    Verifica si un usuario puede ver un proyecto.
    """
    if not usuario or not proyecto:
        return False

    if es_rol_consulta_general(usuario):
        return True

    return obtener_proyectos_del_usuario(usuario).filter(id=proyecto.id).exists()


# ============================================================
# TUTORÍAS
# ============================================================

def obtener_tutorias_por_usuario(usuario):
    """
    Retorna las tutorías visibles según el rol.
    """

    usuario_sistema = obtener_usuario_sistema(usuario)

    if not usuario_sistema:
        return Tutoria.objects.none()

    queryset = Tutoria.objects.select_related(
        "proyecto",
        "proyecto__maestrante",
        "proyecto__maestrante__usuario",
        "tutor",
        "tutor__usuario",
    ).all()

    if es_rol_consulta_general(usuario_sistema):
        return queryset.order_by("fecha", "hora_inicio", "numero")

    if es_maestrante(usuario_sistema):
        proyectos_ids = obtener_proyectos_del_usuario(usuario_sistema).values_list(
            "id",
            flat=True,
        )

        return queryset.filter(
            proyecto_id__in=proyectos_ids
        ).order_by("fecha", "hora_inicio", "numero")

    if es_tutor(usuario_sistema):
        tutor = Tutor.objects.filter(usuario=usuario_sistema).first()

        if not tutor:
            return Tutoria.objects.none()

        return queryset.filter(
            Q(tutor=tutor) |
            Q(proyecto__asignaciones_tutor__tutor=tutor)
        ).distinct().order_by("fecha", "hora_inicio", "numero")

    return Tutoria.objects.none()


def calcular_progreso_tutorias(proyecto):
    """
    Calcula el avance de tutorías de un proyecto.

    Regla:
    Para cierre se necesitan 8 tutorías realizadas.
    """

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
    realizadas = tutorias.filter(estado="realizada").count()
    pendientes = max(TOTAL_TUTORIAS_REQUERIDAS - realizadas, 0)
    porcentaje = calcular_porcentaje(realizadas, TOTAL_TUTORIAS_REQUERIDAS)

    return {
        "total": total,
        "realizadas": realizadas,
        "pendientes": pendientes,
        "porcentaje": porcentaje,
        "cumple": realizadas >= TOTAL_TUTORIAS_REQUERIDAS,
    }


def obtener_tutorias_pendientes(usuario=None):
    """
    Obtiene tutorías pendientes.
    Si recibe usuario, aplica permisos por rol.
    """

    if usuario:
        queryset = obtener_tutorias_por_usuario(usuario)
    else:
        queryset = Tutoria.objects.all()

    return queryset.exclude(
        estado="realizada"
    ).order_by("fecha", "hora_inicio", "numero")


# ============================================================
# ASISTENCIAS Y GRABACIONES
# ============================================================

def obtener_asistencias_tutoria(tutoria):
    if not tutoria:
        return AsistenciaTutoria.objects.none()

    return AsistenciaTutoria.objects.filter(
        tutoria=tutoria
    ).select_related("usuario", "registrado_por")


def obtener_grabaciones_tutoria(tutoria):
    if not tutoria:
        return Grabacion.objects.none()

    return Grabacion.objects.filter(
        tutoria=tutoria
    ).select_related("proyecto", "tutoria", "registrado_por")


# ============================================================
# EVIDENCIAS
# ============================================================

def obtener_evidencias_por_usuario(usuario):
    """
    Retorna evidencias visibles según el rol.
    """

    usuario_sistema = obtener_usuario_sistema(usuario)

    if not usuario_sistema:
        return Evidencia.objects.none()

    queryset = Evidencia.objects.select_related(
        "proyecto",
        "tutoria",
        "cargado_por",
    ).all()

    if es_rol_consulta_general(usuario_sistema):
        return queryset.order_by("-fecha_carga", "-id")

    proyectos_ids = obtener_proyectos_del_usuario(usuario_sistema).values_list(
        "id",
        flat=True,
    )

    return queryset.filter(
        proyecto_id__in=proyectos_ids
    ).order_by("-fecha_carga", "-id")


def obtener_evidencias_por_tutoria(tutoria):
    if not tutoria:
        return Evidencia.objects.none()

    return Evidencia.objects.filter(
        tutoria=tutoria
    ).select_related("proyecto", "tutoria", "cargado_por")


def obtener_evidencias_observadas(proyecto=None):
    """
    Evidencias observadas.
    Sirve para reportes y dashboard.
    """

    queryset = Evidencia.objects.filter(
        estado="observada"
    ).select_related("proyecto", "tutoria", "cargado_por")

    if proyecto:
        queryset = queryset.filter(proyecto=proyecto)

    return queryset.order_by("-fecha_carga", "-id")


def calcular_progreso_evidencias(proyecto):
    """
    Calcula avance de evidencias.

    Regla:
    Para cierre se necesitan 8 evidencias validadas.
    """

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
    pendientes = max(TOTAL_EVIDENCIAS_REQUERIDAS - validadas, 0)
    porcentaje = calcular_porcentaje(validadas, TOTAL_EVIDENCIAS_REQUERIDAS)

    return {
        "total": total,
        "validadas": validadas,
        "observadas": observadas,
        "pendientes": pendientes,
        "porcentaje": porcentaje,
        "cumple": validadas >= TOTAL_EVIDENCIAS_REQUERIDAS,
    }


def obtener_siguiente_numero_version(evidencia):
    """
    Calcula el siguiente número de versión de una evidencia.
    """

    if not evidencia:
        return 1

    ultima_version = EvidenciaVersion.objects.filter(
        evidencia=evidencia
    ).aggregate(
        mayor=Max("numero_version")
    ).get("mayor")

    if not ultima_version:
        return 1

    return ultima_version + 1


def obtener_historial_evidencia(evidencia):
    """
    Retorna versiones y validaciones de una evidencia.
    """

    if not evidencia:
        return {
            "versiones": EvidenciaVersion.objects.none(),
            "validaciones": ValidacionEvidencia.objects.none(),
        }

    versiones = EvidenciaVersion.objects.filter(
        evidencia=evidencia
    ).select_related("creado_por").order_by("-numero_version", "-id")

    validaciones = ValidacionEvidencia.objects.filter(
        evidencia=evidencia
    ).select_related("tutor", "tutor__usuario", "validado_por").order_by(
        "-fecha_validacion",
        "-id",
    )

    return {
        "versiones": versiones,
        "validaciones": validaciones,
    }


def usuario_puede_subir_evidencia(usuario):
    """
    Principalmente maestrante.
    También se puede permitir a coordinador/supervisor en casos administrativos.
    """
    return es_maestrante(usuario) or es_rol_consulta_general(usuario)


def usuario_puede_validar_evidencia(usuario):
    """
    Principalmente tutor.
    También coordinador/supervisor pueden revisar si el sistema lo requiere.
    """
    return es_tutor(usuario) or es_rol_consulta_general(usuario)


# ============================================================
# ARTÍCULO CIENTÍFICO
# ============================================================

def obtener_articulo_proyecto(proyecto):
    """
    Obtiene el artículo de un proyecto.
    No lo crea automáticamente para evitar errores si la tabla tiene campos NOT NULL
    no contemplados en el modelo.
    """

    if not proyecto:
        return None

    return Articulo.objects.filter(proyecto=proyecto).first()


def calcular_avance_articulo(articulo):
    """
    Calcula avance del artículo según secciones llenas.
    """

    if not articulo:
        return {
            "secciones_completas": 0,
            "total_secciones": len(SECCIONES_ARTICULO),
            "porcentaje": 0,
            "detalle": [],
        }

    detalle = []
    completas = 0

    for seccion in SECCIONES_ARTICULO:
        contenido = getattr(articulo, seccion, None)
        esta_completa = bool(contenido and str(contenido).strip())

        if esta_completa:
            completas += 1

        detalle.append({
            "seccion": seccion,
            "completa": esta_completa,
            "contenido": contenido,
        })

    porcentaje = calcular_porcentaje(completas, len(SECCIONES_ARTICULO))

    return {
        "secciones_completas": completas,
        "total_secciones": len(SECCIONES_ARTICULO),
        "porcentaje": porcentaje,
        "detalle": detalle,
    }


# ============================================================
# CIERRE DEL PROCESO
# ============================================================

def puede_cerrar_proceso(proyecto):
    """
    Regla principal de cierre:

    Solo se puede cerrar si:
    - existen al menos 8 tutorías realizadas
    - existen al menos 8 evidencias validadas
    """

    progreso_tutorias = calcular_progreso_tutorias(proyecto)
    progreso_evidencias = calcular_progreso_evidencias(proyecto)

    return (
        progreso_tutorias["realizadas"] >= TOTAL_TUTORIAS_REQUERIDAS
        and progreso_evidencias["validadas"] >= TOTAL_EVIDENCIAS_REQUERIDAS
    )


def obtener_checklist_cierre(proyecto):
    """
    Devuelve el checklist completo para mostrar en template.
    """

    progreso_tutorias = calcular_progreso_tutorias(proyecto)
    progreso_evidencias = calcular_progreso_evidencias(proyecto)
    articulo = obtener_articulo_proyecto(proyecto)
    avance_articulo = calcular_avance_articulo(articulo)

    envio_revista_registrado = False

    if articulo:
        envio_revista_registrado = bool(
            articulo.revista_nombre and articulo.fecha_envio_revista
        )

    checklist = [
        {
            "codigo": "TUT-08",
            "nombre": "8 tutorías realizadas",
            "cumplido": progreso_tutorias["cumple"],
            "detalle": f'{progreso_tutorias["realizadas"]}/8 tutorías realizadas',
        },
        {
            "codigo": "EVI-08",
            "nombre": "8 evidencias validadas",
            "cumplido": progreso_evidencias["cumple"],
            "detalle": f'{progreso_evidencias["validadas"]}/8 evidencias validadas',
        },
        {
            "codigo": "ART-SEC",
            "nombre": "Artículo científico por secciones",
            "cumplido": avance_articulo["porcentaje"] == 100,
            "detalle": f'{avance_articulo["porcentaje"]}% de avance del artículo',
        },
        {
            "codigo": "REV-ENV",
            "nombre": "Envío del artículo a revista",
            "cumplido": envio_revista_registrado,
            "detalle": "Envío registrado" if envio_revista_registrado else "Pendiente de registrar envío",
        },
    ]

    return {
        "proyecto": proyecto,
        "progreso_tutorias": progreso_tutorias,
        "progreso_evidencias": progreso_evidencias,
        "articulo": articulo,
        "avance_articulo": avance_articulo,
        "items": checklist,
        "puede_cerrar": puede_cerrar_proceso(proyecto),
    }


# ============================================================
# NOTIFICACIONES
# ============================================================

def obtener_notificaciones_usuario(usuario, solo_no_leidas=False):
    """
    Obtiene notificaciones del usuario.
    """

    usuario_sistema = obtener_usuario_sistema(usuario)

    if not usuario_sistema:
        return Notificacion.objects.none()

    queryset = Notificacion.objects.filter(
        usuario=usuario_sistema
    ).order_by("-creado_en", "-id")

    if solo_no_leidas:
        queryset = queryset.filter(leida=False)

    return queryset


def contar_notificaciones_no_leidas(usuario):
    return obtener_notificaciones_usuario(
        usuario,
        solo_no_leidas=True,
    ).count()


# ============================================================
# DASHBOARD
# ============================================================

def obtener_dashboard_seguimiento(usuario):
    """
    Prepara toda la data del dashboard de seguimiento.
    """

    usuario_sistema = obtener_usuario_sistema(usuario)
    proyecto = obtener_proyecto_del_usuario(usuario_sistema)

    progreso_tutorias = calcular_progreso_tutorias(proyecto)
    progreso_evidencias = calcular_progreso_evidencias(proyecto)

    articulo = obtener_articulo_proyecto(proyecto)
    avance_articulo = calcular_avance_articulo(articulo)

    tutorias_pendientes = obtener_tutorias_pendientes(
        usuario_sistema
    )[:5]

    evidencias_observadas = obtener_evidencias_observadas(
        proyecto
    )[:5]

    notificaciones = obtener_notificaciones_usuario(
        usuario_sistema
    )[:5]

    return {
        "usuario_sistema": usuario_sistema,
        "rol": obtener_nombre_rol(usuario_sistema),
        "proyecto": proyecto,
        "progreso_tutorias": progreso_tutorias,
        "progreso_evidencias": progreso_evidencias,
        "articulo": articulo,
        "avance_articulo": avance_articulo,
        "puede_cerrar": puede_cerrar_proceso(proyecto),
        "tutorias_pendientes": tutorias_pendientes,
        "evidencias_observadas": evidencias_observadas,
        "notificaciones": notificaciones,
        "notificaciones_no_leidas": contar_notificaciones_no_leidas(usuario_sistema),
    }


# ============================================================
# REPORTES
# ============================================================

def obtener_reportes_seguimiento():
    """
    Datos básicos para la pantalla de reportes.
    Coordinador y supervisor serán quienes normalmente usen esto.
    """

    maestrantes_por_estado = Maestrante.objects.values(
        "estado"
    ).annotate(
        total=Count("id")
    ).order_by("estado")

    tutorias_por_estado = Tutoria.objects.values(
        "estado"
    ).annotate(
        total=Count("id")
    ).order_by("estado")

    evidencias_por_estado = Evidencia.objects.values(
        "estado"
    ).annotate(
        total=Count("id")
    ).order_by("estado")

    proyectos_por_estado = ProyectoTitulacion.objects.values(
        "estado"
    ).annotate(
        total=Count("id")
    ).order_by("estado")

    tutorias_pendientes = Tutoria.objects.exclude(
        estado="realizada"
    ).select_related(
        "proyecto",
        "tutor",
        "tutor__usuario",
    ).order_by("fecha", "hora_inicio")[:20]

    evidencias_observadas = Evidencia.objects.filter(
        estado="observada"
    ).select_related(
        "proyecto",
        "tutoria",
        "cargado_por",
    ).order_by("-fecha_carga")[:20]

    tutores_asignados = AsignacionTutor.objects.select_related(
        "proyecto",
        "tutor",
        "tutor__usuario",
    ).order_by("-fecha_asignacion", "-id")[:20]

    proyectos = ProyectoTitulacion.objects.select_related(
        "maestrante",
        "maestrante__usuario",
    ).order_by("-id")[:20]

    avance_por_proyecto = []

    for proyecto in proyectos:
        avance_por_proyecto.append({
            "proyecto": proyecto,
            "progreso_tutorias": calcular_progreso_tutorias(proyecto),
            "progreso_evidencias": calcular_progreso_evidencias(proyecto),
            "puede_cerrar": puede_cerrar_proceso(proyecto),
        })

    return {
        "total_maestrantes": Maestrante.objects.count(),
        "total_proyectos": ProyectoTitulacion.objects.count(),
        "total_tutorias": Tutoria.objects.count(),
        "total_evidencias": Evidencia.objects.count(),
        "maestrantes_por_estado": maestrantes_por_estado,
        "tutorias_por_estado": tutorias_por_estado,
        "evidencias_por_estado": evidencias_por_estado,
        "proyectos_por_estado": proyectos_por_estado,
        "tutorias_pendientes": tutorias_pendientes,
        "evidencias_observadas": evidencias_observadas,
        "tutores_asignados": tutores_asignados,
        "avance_por_proyecto": avance_por_proyecto,
    }