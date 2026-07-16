"""Motor único de reglas para las modalidades de titulación."""

from copy import deepcopy

from django.db import DatabaseError, ProgrammingError

from .models import ConfiguracionModalidadPrograma, ModalidadProyecto, TipoArchivo


CATALOGO_TIPOS_EVIDENCIA = (
    ("busqueda_bibliografica", "Búsqueda bibliográfica"),
    ("titulo", "Título"),
    ("introduccion", "Introducción"),
    ("planteamiento_problema", "Planteamiento del problema"),
    ("marco_teorico", "Marco teórico"),
    ("metodologia", "Metodología"),
    ("analisis", "Análisis"),
    ("resultados", "Resultados"),
    ("conclusiones", "Conclusiones"),
    ("referencias", "Referencias"),
    ("documento_final", "Documento final"),
    ("anexos", "Anexos"),
    ("plan_estudio", "Plan de estudio"),
    ("banco_preguntas", "Banco de preguntas"),
    ("simulacion", "Simulación"),
    ("acta_resultado", "Acta o resultado"),
    ("otro", "Otro"),
)

ETIQUETAS_EVIDENCIA = dict(CATALOGO_TIPOS_EVIDENCIA)

REGLAS_BASE = {
    ModalidadProyecto.ARTICULO: {
        "codigo": ModalidadProyecto.ARTICULO,
        "nombre": "Artículo científico",
        "descripcion": "Desarrollo de un artículo por secciones y registro de su envío a revista.",
        "tipos_evidencia": (
            "busqueda_bibliografica",
            "titulo",
            "introduccion",
            "metodologia",
            "resultados",
            "conclusiones",
            "referencias",
            "otro",
        ),
        "producto_final_nombre": "Artículo completo y enviado a revista",
        "tipo_archivo_final": None,
        "requiere_articulo": True,
        "requiere_envio_revista": True,
    },
    ModalidadProyecto.INVESTIGACION: {
        "codigo": ModalidadProyecto.INVESTIGACION,
        "nombre": "Proyecto de investigación",
        "descripcion": "Trabajo de investigación con documento final revisado y aprobado.",
        "tipos_evidencia": (
            "busqueda_bibliografica",
            "planteamiento_problema",
            "marco_teorico",
            "metodologia",
            "analisis",
            "resultados",
            "conclusiones",
            "documento_final",
            "anexos",
            "otro",
        ),
        "producto_final_nombre": "Documento final del proyecto de investigación",
        "tipo_archivo_final": TipoArchivo.PDF,
        "requiere_articulo": False,
        "requiere_envio_revista": False,
    },
    ModalidadProyecto.EXAMEN: {
        "codigo": ModalidadProyecto.EXAMEN,
        "nombre": "Examen complexivo",
        "descripcion": "Preparación, rendición y registro documental del resultado del examen.",
        "tipos_evidencia": (
            "plan_estudio",
            "banco_preguntas",
            "simulacion",
            "acta_resultado",
            "otro",
        ),
        "producto_final_nombre": "Acta o resolución del resultado del examen",
        "tipo_archivo_final": TipoArchivo.RESOLUCION,
        "requiere_articulo": False,
        "requiere_envio_revista": False,
    },
}


def _modalidad_configurada_activa(programa, modalidad):
    """Busca la fila BD (Fase 7) de una modalidad base semilla.

    Devuelve None si la tabla `modalidades_configuradas` todavía no existe
    (SQL 15 no aplicado) o si no hay fila configurada — en ambos casos el
    llamador debe usar `REGLAS_BASE` como respaldo, preservando el
    comportamiento previo a la Fase 7.
    """
    try:
        from .models import ModalidadConfigurada

        consulta = ModalidadConfigurada.objects.filter(
            tipo_modalidad=modalidad,
            es_semilla_base=True,
        ).filter(models_q_programa_o_global(programa))
        return consulta.order_by("programa_id").first()
    except (DatabaseError, ProgrammingError):
        return None
    except Exception:
        # La tabla puede no existir todavía; nunca debe romper el flujo.
        return None


def models_q_programa_o_global(programa):
    from django.db.models import Q

    if programa is None:
        return Q(programa__isnull=True)
    return Q(programa__isnull=True) | Q(programa=programa)


def _configuracion_otra(programa, *, incluir_inactiva=False):
    if not programa:
        return None
    consulta = ConfiguracionModalidadPrograma.objects.filter(programa=programa)
    if not incluir_inactiva:
        consulta = consulta.filter(esta_activa=True)
    return consulta.first()


def obtener_regla_modalidad(programa, modalidad):
    if modalidad in REGLAS_BASE:
        regla = deepcopy(REGLAS_BASE[modalidad])
        configurada = _modalidad_configurada_activa(programa, modalidad)
        if configurada is not None:
            # BD (Fase 7) manda sobre el texto hardcodeado; las banderas de
            # negocio (requiere_articulo, total_tutorias, etc.) permanecen
            # fijas por tipo de modalidad.
            regla["nombre"] = configurada.nombre
            regla["descripcion"] = configurada.descripcion or regla["descripcion"]
            regla["esta_disponible"] = configurada.esta_activa
            regla["modalidad_configurada_id"] = configurada.id
    elif modalidad == ModalidadProyecto.OTRA:
        configuracion = _configuracion_otra(programa, incluir_inactiva=True)
        if not configuracion:
            return {
                "codigo": ModalidadProyecto.OTRA,
                "nombre": "Otra modalidad",
                "descripcion": "Pendiente de configuración para este programa.",
                "tipos_evidencia": ("otro",),
                "producto_final_nombre": "Producto final por configurar",
                "tipo_archivo_final": TipoArchivo.PDF,
                "requiere_articulo": False,
                "requiere_envio_revista": False,
                "esta_disponible": False,
            }
        regla = {
            "codigo": ModalidadProyecto.OTRA,
            "nombre": configuracion.nombre,
            "descripcion": configuracion.descripcion,
            "tipos_evidencia": tuple(configuracion.tipos_evidencia or ("otro",)),
            "producto_final_nombre": configuracion.producto_final_nombre,
            "tipo_archivo_final": configuracion.tipo_archivo_final,
            "requiere_articulo": False,
            "requiere_envio_revista": False,
            "esta_disponible": configuracion.esta_activa,
        }
    else:
        raise ValueError("Modalidad de titulación no reconocida.")

    regla.setdefault("esta_disponible", True)
    regla["total_tutorias"] = 8
    regla["total_evidencias"] = 8
    regla["evidencias"] = tuple(
        (codigo, ETIQUETAS_EVIDENCIA.get(codigo, codigo.replace("_", " ").title()))
        for codigo in regla["tipos_evidencia"]
    )
    return regla


def modalidades_disponibles(programa, *, incluir_modalidad=None):
    opciones = [
        (codigo, regla["nombre"])
        for codigo, regla in REGLAS_BASE.items()
    ]
    otra = _configuracion_otra(programa)
    if otra:
        opciones.append((ModalidadProyecto.OTRA, otra.nombre))
    elif incluir_modalidad == ModalidadProyecto.OTRA:
        opciones.append((ModalidadProyecto.OTRA, "Otra modalidad (configuración inactiva)"))
    return tuple(opciones)


def modalidad_disponible(programa, modalidad):
    return modalidad in {codigo for codigo, _ in modalidades_disponibles(programa)}
