from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from apps.titulacion import models as titulacion_models

from . import models
from .services import calcular_avance_articulo, calcular_porcentaje
from .forms import EvidenciaForm


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
