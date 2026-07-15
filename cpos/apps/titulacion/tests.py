from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db.models import ForeignKey, OneToOneField
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .models import (
    Aprobacion,
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    EstadoProyecto,
    EstadoTutor,
    Grabacion,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    Tutor,
    Tutoria,
    TipoAprobacion,
)
from .services import puede_escribir, rol_usuario
from .storage import eliminar_archivo, guardar_archivo, respuesta_descarga


class TutorModelContractTests(SimpleTestCase):
    def test_modelo_respeta_contrato_de_supabase(self):
        self.assertEqual(Tutor._meta.db_table, "tutores")
        self.assertIsInstance(Tutor._meta.get_field("usuario"), OneToOneField)
        self.assertEqual(Tutor._meta.get_field("usuario").column, "usuario_id")
        self.assertEqual(Tutor._meta.get_field("titulo_academico").max_length, 200)
        self.assertEqual(Tutor._meta.get_field("linea_investigacion").max_length, 250)
        self.assertEqual(
            {valor for valor, _ in EstadoTutor.choices},
            {"disponible", "no_disponible", "inactivo"},
        )


class TutorRoutesTests(SimpleTestCase):
    def test_rutas_crud(self):
        self.assertEqual(reverse("titulacion:tutores_list"), "/titulacion/tutores/")
        self.assertEqual(
            reverse("titulacion:tutor_create"), "/titulacion/tutores/crear/"
        )
        self.assertEqual(
            reverse("titulacion:tutor_detail", kwargs={"pk": 7}),
            "/titulacion/tutores/7/",
        )
        self.assertEqual(
            reverse("titulacion:tutor_update", kwargs={"pk": 7}),
            "/titulacion/tutores/7/editar/",
        )
        self.assertEqual(
            reverse("titulacion:tutor_toggle_estado", kwargs={"pk": 7}),
            "/titulacion/tutores/7/estado/",
        )


class TitulacionModelContractTests(SimpleTestCase):
    def test_modelos_apuntan_a_tablas_existentes_sin_duplicarlas(self):
        contratos = {
            ProyectoTitulacion: "proyectos_titulacion",
            AsignacionTutor: "asignaciones_tutor",
            Tutoria: "tutorias",
            AsistenciaTutoria: "asistencias_tutoria",
            ReprogramacionTutoria: "reprogramaciones_tutoria",
            ArchivoProyecto: "archivos_proyecto",
            Grabacion: "grabaciones",
            Articulo: "articulos",
            SolicitudCambioTema: "solicitudes_cambio_tema",
            Aprobacion: "aprobaciones",
        }
        for modelo, tabla in contratos.items():
            with self.subTest(modelo=modelo.__name__):
                self.assertEqual(modelo._meta.db_table, tabla)
                self.assertFalse(modelo._meta.managed)

    def test_relaciones_reutilizan_accounts_y_titulacion(self):
        self.assertIsInstance(
            ProyectoTitulacion._meta.get_field("maestrante"), ForeignKey
        )
        self.assertEqual(
            ProyectoTitulacion._meta.get_field("maestrante").related_model._meta.db_table,
            "maestrantes",
        )
        self.assertIsInstance(
            AsistenciaTutoria._meta.get_field("tutoria"), OneToOneField
        )
        self.assertEqual(
            {valor for valor, _ in EstadoProyecto.choices},
            {"borrador", "en_revision", "observado", "aprobado", "rechazado", "cerrado"},
        )
        self.assertIn(
            "archivo_proyecto",
            {valor for valor, _ in TipoAprobacion.choices},
        )
        for campo in ("nombre_original", "extension", "tamano_bytes"):
            self.assertIsNotNone(Grabacion._meta.get_field(campo))


class TitulacionRoleRulesTests(SimpleTestCase):
    def _usuario(self, rol):
        return SimpleNamespace(rol=SimpleNamespace(nombre=rol))

    def test_supervisor_es_solo_lectura_aunque_tenga_permisos_globales(self):
        supervisor = self._usuario("supervisor")
        self.assertEqual(rol_usuario(supervisor), "supervisor")
        self.assertFalse(puede_escribir(supervisor))

    def test_roles_operativos_pueden_entrar_a_flujos_de_escritura_especificos(self):
        for rol in ("maestrante", "tutor", "coordinador"):
            with self.subTest(rol=rol):
                self.assertTrue(puede_escribir(self._usuario(rol)))


class TitulacionRoutesTests(SimpleTestCase):
    def test_rutas_del_flujo_academico(self):
        casos = {
            "proyecto_create": (None, "/titulacion/proyectos/crear/"),
            "proyecto_detail": ({"pk": 7}, "/titulacion/proyectos/7/"),
            "proyecto_revisar": ({"pk": 7}, "/titulacion/proyectos/7/revisar/"),
            "asignacion_create": ({"pk": 7}, "/titulacion/proyectos/7/asignar-tutor/"),
            "tutoria_create": ({"pk": 7}, "/titulacion/proyectos/7/tutorias/programar/"),
            "tutoria_registrar": ({"pk": 8}, "/titulacion/tutorias/8/registrar/"),
            "grabacion_create": ({"pk": 8}, "/titulacion/tutorias/8/grabaciones/registrar/"),
            "articulo_edit": ({"proyecto_pk": 7}, "/titulacion/proyectos/7/articulo/editar/"),
            "cambio_tema_create": ({"proyecto_pk": 7}, "/titulacion/proyectos/7/cambio-tema/"),
            "archivo_download": ({"pk": 9}, "/titulacion/archivos/9/descargar/"),
            "archivo_revisar": ({"pk": 9}, "/titulacion/archivos/9/revisar/"),
            "grabacion_download": ({"pk": 9}, "/titulacion/grabaciones/9/descargar/"),
            "grabacion_enlace": ({"pk": 9}, "/titulacion/grabaciones/9/abrir/"),
        }
        for nombre, (kwargs, ruta) in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    reverse(f"titulacion:{nombre}", kwargs=kwargs),
                    ruta,
                )


class TitulacionStorageTests(SimpleTestCase):
    def test_guarda_y_entrega_pdf_local_privado(self):
        with TemporaryDirectory() as directorio:
            with override_settings(BASE_DIR=Path(directorio)), patch.dict(
                "os.environ",
                {"TITULACION_STORAGE_BACKEND": "local"},
            ):
                subido = SimpleUploadedFile(
                    "proyecto.pdf",
                    b"%PDF-1.4\ncontenido de prueba\n%%EOF",
                    content_type="application/pdf",
                )
                datos = guardar_archivo(
                    subido,
                    categoria="pruebas",
                    proyecto_id=4,
                    extensiones={"pdf"},
                    limite_bytes=1024,
                )
                self.assertTrue(datos["referencia"].startswith("local:pruebas/4/"))
                respuesta = respuesta_descarga(datos["referencia"], "proyecto.pdf")
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("attachment", respuesta["Content-Disposition"])
                respuesta.close()
                eliminar_archivo(datos["referencia"])

    def test_rechaza_archivo_disfrazado_de_pdf(self):
        subido = SimpleUploadedFile(
            "falso.pdf",
            b"esto no es un PDF",
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            guardar_archivo(
                subido,
                categoria="pruebas",
                proyecto_id=4,
                extensiones={"pdf"},
                limite_bytes=1024,
            )
