from datetime import time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from apps.titulacion import models as titulacion_models

from . import models
from .services import (
    asistencia_es_completa,
    calcular_avance_articulo,
    calcular_porcentaje,
    obtener_estado_integridad_tutoria,
    tutoria_ya_finalizo,
    usuario_puede_validar_evidencia,
)
from .forms import (
    AsistenciaTutoriaForm,
    EvidenciaForm,
    GrabacionForm,
    ValidacionEvidenciaForm,
)


class ContratoModelosSeguimientoTests(SimpleTestCase):
    def test_reutiliza_los_modelos_oficiales_de_titulacion(self):
        self.assertIs(models.ProyectoTitulacion, titulacion_models.ProyectoTitulacion)
        self.assertIs(models.Tutoria, titulacion_models.Tutoria)
        self.assertIs(models.AsistenciaTutoria, titulacion_models.AsistenciaTutoria)
        self.assertIs(models.Grabacion, titulacion_models.Grabacion)
        self.assertIs(models.Articulo, titulacion_models.Articulo)

    def test_evidencia_refleja_el_contrato_real_de_postgresql(self):
        self.assertEqual(models.Evidencia._meta.db_table, "evidencias")
        self.assertFalse(models.Evidencia._meta.managed)
        campos = {campo.name for campo in models.Evidencia._meta.fields}
        self.assertIn("archivo_url", campos)
        self.assertIn("subido_por", campos)
        self.assertIn("fecha_creacion", campos)
        self.assertNotIn("archivo", campos)
        self.assertNotIn("cargado_por", campos)
        self.assertNotIn("fecha_carga", campos)

    def test_validacion_usa_estado_resultado(self):
        campos = {campo.name for campo in models.ValidacionEvidencia._meta.fields}
        self.assertIn("estado_resultado", campos)
        self.assertNotIn("estado", campos)

    def test_modelos_fase6_reflejan_historial_y_versiones(self):
        campos_grabacion = {
            campo.name for campo in titulacion_models.Grabacion._meta.fields
        }
        self.assertTrue(
            {"numero_version", "esta_activa", "reemplaza_grabacion"}
            <= campos_grabacion
        )
        campos_version = {campo.name for campo in models.EvidenciaVersion._meta.fields}
        self.assertIn("estado", campos_version)
        campos_validacion = {
            campo.name for campo in models.ValidacionEvidencia._meta.fields
        }
        self.assertIn("evidencia_version", campos_validacion)
        self.assertEqual(
            titulacion_models.AsistenciaTutoriaHistorial._meta.db_table,
            "asistencias_tutoria_historial",
        )


class RutasPrivadasSeguimientoTests(SimpleTestCase):
    def test_rutas_de_descarga_y_apertura(self):
        self.assertEqual(
            reverse("seguimiento:grabacion_download", args=(9,)),
            "/seguimiento/grabaciones/9/descargar/",
        )
        self.assertEqual(
            reverse("seguimiento:grabacion_enlace", args=(9,)),
            "/seguimiento/grabaciones/9/abrir/",
        )
        self.assertEqual(
            reverse("seguimiento:descargar_evidencia", args=(7,)),
            "/seguimiento/evidencias/7/descargar/",
        )
        self.assertEqual(
            reverse("seguimiento:descargar_version", args=(3,)),
            "/seguimiento/evidencias/versiones/3/descargar/",
        )


class CalculosSeguimientoTests(SimpleTestCase):
    def test_porcentaje_controla_vacios_y_limites(self):
        self.assertEqual(calcular_porcentaje(1, 0), 0)
        self.assertEqual(calcular_porcentaje(4, 8), 50)
        self.assertEqual(calcular_porcentaje(12, 8), 100)

    def test_avance_articulo_cuenta_solo_secciones_con_contenido(self):
        articulo = SimpleNamespace(
            titulo="Título",
            introduccion="Introducción",
            metodologia="  ",
            resultados=None,
            conclusiones="Conclusiones",
            referencias="Referencias",
        )
        avance = calcular_avance_articulo(articulo)
        self.assertEqual(avance["secciones_completas"], 4)
        self.assertEqual(avance["total_secciones"], 6)
        self.assertEqual(avance["porcentaje"], 67)

    @patch("apps.seguimiento.forms.obtener_regla_modalidad")
    def test_formulario_evidencia_usa_categorias_de_la_modalidad(self, regla):
        regla.return_value = {
            "nombre": "Examen complexivo",
            "evidencias": (("plan_estudio", "Plan de estudio"), ("simulacion", "Simulación")),
        }
        proyecto = SimpleNamespace(
            modalidad="examen_complexivo",
            maestrante=SimpleNamespace(programa=SimpleNamespace(pk=3)),
        )
        formulario = EvidenciaForm(proyecto=proyecto)
        self.assertEqual(
            tuple(formulario.fields["tipo_avance"].choices),
            regla.return_value["evidencias"],
        )

    def test_asistencia_completa_exige_ambos_participantes(self):
        self.assertFalse(asistencia_es_completa(None))
        self.assertFalse(
            asistencia_es_completa(
                SimpleNamespace(asistio_tutor=True, asistio_maestrante=False)
            )
        )
        self.assertTrue(
            asistencia_es_completa(
                SimpleNamespace(asistio_tutor=True, asistio_maestrante=True)
            )
        )

    def test_tutoria_futura_no_ha_finalizado(self):
        manana = timezone.localdate() + timedelta(days=1)
        tutoria = SimpleNamespace(
            fecha=manana,
            hora_fin=time(10, 0),
        )
        self.assertFalse(tutoria_ya_finalizo(tutoria))


class FormulariosFase6Tests(SimpleTestCase):
    def test_realizada_exige_asistencia_de_tutor_y_maestrante(self):
        formulario = AsistenciaTutoriaForm(
            data={
                "estado_tutoria": "realizada",
                "asistio_tutor": "on",
                "observaciones": "Sesion academica.",
            }
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("requiere asistencia", str(formulario.non_field_errors()))

    def test_no_realizada_exige_observacion(self):
        formulario = AsistenciaTutoriaForm(
            data={"estado_tutoria": "no_realizada"}
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("observaciones", formulario.errors)

    def test_correccion_exige_motivo_y_habilita_cancelacion(self):
        formulario = AsistenciaTutoriaForm(
            data={
                "estado_tutoria": "cancelada",
                "observaciones": "Cancelada por fuerza mayor.",
            },
            es_correccion=True,
            permite_cancelar=True,
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("motivo_correccion", formulario.errors)
        self.assertIn(
            "cancelada",
            {valor for valor, _ in formulario.fields["estado_tutoria"].choices},
        )

    def test_grabacion_rechaza_http(self):
        formulario = GrabacionForm(
            data={
                "tipo_grabacion": "enlace",
                "enlace_grabacion": "http://example.test/grabacion",
            }
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("enlace_grabacion", formulario.errors)

    def test_observacion_y_rechazo_exigen_explicacion(self):
        for estado in ("observada", "rechazada"):
            formulario = ValidacionEvidenciaForm(
                data={"estado_resultado": estado, "observaciones": ""}
            )
            self.assertFalse(formulario.is_valid())
            self.assertIn("observaciones", formulario.errors)


class AlcanceFase6Tests(SimpleTestCase):
    @patch("apps.seguimiento.services.usuario_puede_ver_proyecto", return_value=True)
    @patch("apps.seguimiento.services.usuario_tiene_permiso", return_value=True)
    @patch("apps.seguimiento.services.es_tutor", return_value=True)
    def test_solo_tutor_de_la_tutoria_puede_validar(
        self,
        _es_tutor,
        _permiso,
        _visible,
    ):
        usuario = SimpleNamespace(pk=9)
        evidencia = SimpleNamespace(
            proyecto=SimpleNamespace(pk=1),
            tutoria=SimpleNamespace(tutor=SimpleNamespace(usuario_id=9)),
        )
        self.assertTrue(usuario_puede_validar_evidencia(usuario, evidencia))
        evidencia.tutoria.tutor.usuario_id = 10
        self.assertFalse(usuario_puede_validar_evidencia(usuario, evidencia))

    @patch("apps.seguimiento.services.Grabacion.objects")
    @patch("apps.seguimiento.services.Evidencia.objects")
    @patch("apps.seguimiento.services.AsistenciaTutoria.objects")
    def test_integridad_exige_evidencia_validada(
        self,
        asistencias,
        evidencias,
        grabaciones,
    ):
        asistencias.filter.return_value.first.return_value = SimpleNamespace(
            asistio_tutor=True,
            asistio_maestrante=True,
        )
        evidencias.filter.return_value.first.return_value = SimpleNamespace(
            estado="en_revision"
        )
        grabaciones.filter.return_value.first.return_value = SimpleNamespace(pk=3)
        tutoria = SimpleNamespace(estado="realizada")
        estado = obtener_estado_integridad_tutoria(tutoria)
        self.assertTrue(estado["realizada_valida"])
        self.assertFalse(estado["completa"])


class PlantillasFase6Tests(SimpleTestCase):
    def test_compilan_plantillas_relevantes(self):
        for nombre in (
            "seguimiento/dashboard.html",
            "seguimiento/tutorias_list.html",
            "seguimiento/tutoria_detail.html",
            "seguimiento/tutoria_form.html",
            "seguimiento/evidencias_list.html",
            "seguimiento/evidencia_detail.html",
            "seguimiento/evidencia_form.html",
            "seguimiento/evidencia_validar.html",
            "seguimiento/evidencia_historial.html",
        ):
            self.assertIsNotNone(get_template(nombre))


class ChecklistCierreFase7Tests(SimpleTestCase):
    """El envío a revista ya no es requisito bloqueante para cerrar (Fase 7)."""

    def test_checklist_no_incluye_item_de_envio_a_revista(self):
        import inspect

        from . import services

        codigo_fuente = inspect.getsource(services.obtener_checklist_cierre)
        self.assertNotIn("REV-ENV", codigo_fuente)
        self.assertIn(
            "ya NO bloquea el cierre",
            codigo_fuente,
        )


class ContratoModelosFase7Tests(SimpleTestCase):
    """Contrato mínimo de los modelos nuevos de Fase 7 (7A-7D)."""

    def test_onboarding_maestrante(self):
        modelo = titulacion_models.OnboardingMaestrante
        self.assertEqual(modelo._meta.db_table, "onboarding_maestrantes")
        self.assertFalse(modelo._meta.managed)
        campos = {campo.name for campo in modelo._meta.fields}
        self.assertTrue(
            {"proyecto", "maestrante", "estado", "modalidad_seleccionada"} <= campos
        )

    def test_modalidad_configurada_y_etapa_producto(self):
        modalidad = titulacion_models.ModalidadConfigurada
        etapa = titulacion_models.EtapaProducto
        self.assertEqual(modalidad._meta.db_table, "modalidades_configuradas")
        self.assertEqual(etapa._meta.db_table, "etapas_producto")
        campos_etapa = {campo.name for campo in etapa._meta.fields}
        self.assertTrue({"modalidad", "orden", "codigo", "es_obligatoria"} <= campos_etapa)

    def test_entrega_etapa_inmutable_tras_aprobacion_por_contrato(self):
        entrega = titulacion_models.EntregaEtapa
        campos = {campo.name for campo in entrega._meta.fields}
        self.assertTrue(
            {"proyecto", "etapa", "numero_version", "estado", "coordinador_responsable"}
            <= campos
        )

    def test_tutoria_admite_novena_excepcional(self):
        campos = {campo.name for campo in titulacion_models.Tutoria._meta.fields}
        self.assertIn("es_excepcional", campos)
        campos_autorizacion = {
            campo.name
            for campo in titulacion_models.AutorizacionNovenaTutoria._meta.fields
        }
        self.assertTrue({"proyecto", "tutoria", "motivo", "autorizado_por"} <= campos_autorizacion)

    def test_tutoria_numero_maximo_permitido_es_nueve(self):
        tutoria = titulacion_models.Tutoria(numero_tutoria=10, proyecto_id=1)
        with self.assertRaises(Exception):
            tutoria.clean()

    def test_examen_complexivo_y_escala_calificacion(self):
        examen = titulacion_models.ExamenComplexivo
        escala = titulacion_models.EscalaCalificacion
        self.assertEqual(examen._meta.db_table, "examenes_complexivos")
        self.assertEqual(escala._meta.db_table, "escalas_calificacion")
        campos_examen = {campo.name for campo in examen._meta.fields}
        self.assertTrue(
            {"proyecto", "numero_intento", "resultado", "calificacion", "escala"}
            <= campos_examen
        )

    def test_maestrante_tiene_modulo_actual(self):
        from apps.accounts import models as accounts_models

        campos = {campo.name for campo in accounts_models.Maestrante._meta.fields}
        self.assertIn("modulo_actual", campos)


class PlantillasFase7Tests(SimpleTestCase):
    def test_compilan_plantillas_relevantes(self):
        for nombre in (
            "titulacion/onboarding.html",
            "titulacion/modalidades_configuradas_list.html",
            "titulacion/examenes_complexivos_list.html",
            "seguimiento/entregas_etapa.html",
            "seguimiento/entrega_etapa_form.html",
            "seguimiento/entrega_etapa_evaluar.html",
        ):
            self.assertIsNotNone(get_template(nombre))


class OnboardingGateFase7Tests(SimpleTestCase):
    """Verifica que el gate de onboarding (Fase 7A) sea un control real de
    backend (decorator), no solo un botón oculto en el template."""

    def test_decorator_redirige_a_onboarding_si_no_esta_completado(self):
        from . import views as seguimiento_views

        @seguimiento_views.usuario_activo_y_onboarding_completado
        def vista_falsa(request):
            return "vista_alcanzada"

        usuario_falso = SimpleNamespace(is_authenticated=True)
        request_falso = SimpleNamespace(user=usuario_falso, session={})

        with patch(
                 "apps.accounts.decorators.verificar_usuario_activo", return_value=True
             ), \
             patch(
                 "apps.accounts.decorators.UsuarioCPOS",
                 SimpleNamespace,
             ), \
             patch.object(
                 seguimiento_views, "onboarding_completado", return_value=False
             ), \
             patch.object(seguimiento_views.messages, "warning", return_value=None):
            respuesta = vista_falsa(request_falso)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("onboarding", respuesta.url)

    def test_decorator_permite_paso_si_onboarding_completado(self):
        from . import views as seguimiento_views

        @seguimiento_views.usuario_activo_y_onboarding_completado
        def vista_falsa(request):
            return "vista_alcanzada"

        usuario_falso = SimpleNamespace(is_authenticated=True)
        request_falso = SimpleNamespace(user=usuario_falso, session={})

        with patch(
                 "apps.accounts.decorators.verificar_usuario_activo", return_value=True
             ), \
             patch(
                 "apps.accounts.decorators.UsuarioCPOS",
                 SimpleNamespace,
             ), \
             patch.object(
                 seguimiento_views, "onboarding_completado", return_value=True
             ):
            respuesta = vista_falsa(request_falso)
        self.assertEqual(respuesta, "vista_alcanzada")

    def test_onboarding_completado_no_afecta_roles_distintos_de_maestrante(self):
        from apps.titulacion.services import onboarding_completado

        usuario_falso = SimpleNamespace(rol=SimpleNamespace(nombre="coordinador"))
        self.assertTrue(onboarding_completado(usuario_falso))

    def test_maestrante_no_elegible_por_modulo_bajo(self):
        from apps.titulacion.services import maestrante_es_elegible_onboarding

        maestrante_falso = SimpleNamespace(modulo_actual=3)
        self.assertFalse(maestrante_es_elegible_onboarding(maestrante_falso))

    def test_maestrante_elegible_desde_modulo_cinco(self):
        from apps.titulacion.services import maestrante_es_elegible_onboarding

        maestrante_falso = SimpleNamespace(modulo_actual=5)
        self.assertTrue(maestrante_es_elegible_onboarding(maestrante_falso))


class NovenaTutoriaFase7Tests(SimpleTestCase):
    def test_solo_coordinador_puede_autorizar_novena_tutoria(self):
        from apps.titulacion.services import puede_autorizar_novena_tutoria

        coordinador = SimpleNamespace(rol=SimpleNamespace(nombre="coordinador"))
        maestrante = SimpleNamespace(rol=SimpleNamespace(nombre="maestrante"))
        tutor = SimpleNamespace(rol=SimpleNamespace(nombre="tutor"))
        with patch(
            "apps.titulacion.services.usuario_tiene_permiso", return_value=False
        ):
            self.assertTrue(puede_autorizar_novena_tutoria(coordinador))
            self.assertFalse(puede_autorizar_novena_tutoria(maestrante))
            self.assertFalse(puede_autorizar_novena_tutoria(tutor))

    def test_maestrante_no_puede_autorizar_su_propia_novena(self):
        # `autorizar_novena_tutoria` valida el permiso mediante
        # `puede_autorizar_novena_tutoria` antes de tocar la base de datos;
        # se prueba la función de permiso directamente (ver arriba) porque
        # el cuerpo completo usa @transaction.atomic y esta suite no tiene
        # acceso a una base de datos real (SimpleTestCase).
        import inspect

        from apps.titulacion.services import autorizar_novena_tutoria

        codigo_fuente = inspect.getsource(autorizar_novena_tutoria)
        self.assertIn("puede_autorizar_novena_tutoria(actor)", codigo_fuente)
        self.assertIn("raise PermissionDenied", codigo_fuente)

    def test_formulario_tutoria_solo_ofrece_novena_con_autorizacion(self):
        from apps.titulacion.forms import TutoriaForm

        class TutoriasFalsas:
            def values_list(self, *args, **kwargs):
                return list(range(1, 9))

        proyecto_sin_autorizacion = SimpleNamespace(pk=1, tutorias=TutoriasFalsas())
        with patch(
            "apps.titulacion.forms.AutorizacionNovenaTutoria.objects.filter"
        ) as filtro:
            filtro.return_value.exists.return_value = False
            formulario = TutoriaForm(proyecto=proyecto_sin_autorizacion)
            self.assertEqual(formulario.fields["numero_tutoria"].choices, [])

        proyecto_con_autorizacion = SimpleNamespace(pk=2, tutorias=TutoriasFalsas())
        with patch(
            "apps.titulacion.forms.AutorizacionNovenaTutoria.objects.filter"
        ) as filtro:
            filtro.return_value.exists.return_value = True
            formulario = TutoriaForm(proyecto=proyecto_con_autorizacion)
            self.assertEqual(
                {valor for valor, _ in formulario.fields["numero_tutoria"].choices},
                {9},
            )


class AsignacionTutorFase7Tests(SimpleTestCase):
    """El maestrante nunca puede autoasignarse tutor (7C): la vista exige
    explícitamente el rol coordinador, sin excepciones por permiso."""

    def test_asignacion_create_exige_rol_coordinador(self):
        import inspect

        from apps.titulacion import views as titulacion_views

        codigo_fuente = inspect.getsource(titulacion_views.asignacion_create)
        self.assertIn('_exigir_rol(request, "coordinador")', codigo_fuente)

    def test_exigir_rol_deniega_si_el_rol_no_coincide(self):
        from django.core.exceptions import PermissionDenied

        from apps.titulacion.views import _exigir_rol

        request_falso = SimpleNamespace(
            user=SimpleNamespace(rol=SimpleNamespace(nombre="maestrante"))
        )
        with patch(
            "apps.titulacion.views.rol_usuario", return_value="maestrante"
        ):
            with self.assertRaises(PermissionDenied):
                _exigir_rol(request_falso, "coordinador")


class EntregaEtapaOrdenFase7Tests(SimpleTestCase):
    """La vista de subida refleja en UI el mismo bloqueo de orden que el
    trigger SQL fase7_validar_orden_etapas garantiza en último término."""

    def test_etapa_bloqueada_si_etapa_previa_obligatoria_no_aprobada(self):
        from apps.titulacion.services import etapa_esta_bloqueada

        etapa_actual = SimpleNamespace(es_obligatoria=True, orden=2, modalidad=SimpleNamespace(pk=1))
        etapa_previa = SimpleNamespace(pk=10)
        proyecto_falso = SimpleNamespace(pk=1)

        with patch(
            "apps.titulacion.services.EtapaProducto.objects.filter",
            return_value=[etapa_previa],
        ), patch(
            "apps.titulacion.services.EntregaEtapa.objects.filter"
        ) as filtro_entrega:
            filtro_entrega.return_value.exists.return_value = False
            self.assertTrue(etapa_esta_bloqueada(proyecto_falso, etapa_actual))

    def test_etapa_no_bloqueada_si_no_es_obligatoria(self):
        from apps.titulacion.services import etapa_esta_bloqueada

        etapa_opcional = SimpleNamespace(es_obligatoria=False)
        self.assertFalse(etapa_esta_bloqueada(SimpleNamespace(), etapa_opcional))

    def test_puede_subir_entrega_solo_el_maestrante_propietario(self):
        from apps.titulacion.services import puede_subir_entrega_etapa

        propietario = SimpleNamespace(
            rol=SimpleNamespace(nombre="maestrante"),
            perfil_maestrante=SimpleNamespace(id=1),
        )
        otro = SimpleNamespace(
            rol=SimpleNamespace(nombre="maestrante"),
            perfil_maestrante=SimpleNamespace(id=2),
        )
        proyecto_falso = SimpleNamespace(maestrante_id=1)
        self.assertTrue(puede_subir_entrega_etapa(propietario, proyecto_falso))
        self.assertFalse(puede_subir_entrega_etapa(otro, proyecto_falso))

    def test_solo_coordinador_puede_evaluar_entrega(self):
        from apps.titulacion.services import puede_evaluar_entrega_etapa

        coordinador = SimpleNamespace(rol=SimpleNamespace(nombre="coordinador"))
        supervisor = SimpleNamespace(rol=SimpleNamespace(nombre="supervisor"))
        self.assertTrue(puede_evaluar_entrega_etapa(coordinador))
        self.assertFalse(puede_evaluar_entrega_etapa(supervisor))


class ExamenComplexivoFase7Tests(SimpleTestCase):
    def test_escala_calificacion_rechaza_rango_invertido(self):
        from apps.titulacion.forms import EscalaCalificacionForm

        formulario = EscalaCalificacionForm(
            data={
                "nombre": "Escala estándar",
                "nota_minima": "10",
                "nota_maxima": "5",
                "nota_aprobacion": "7",
                "esta_activa": True,
            }
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("nota_maxima", formulario.errors)
