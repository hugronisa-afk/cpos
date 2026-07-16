from types import SimpleNamespace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db.models import ForeignKey, OneToOneField
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone

from .models import (
    Aprobacion,
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    ConfiguracionModalidadPrograma,
    DocumentoProcesoAprobacion,
    DisponibilidadTutor,
    EstadoProyecto,
    EstadoTutor,
    Grabacion,
    ModalidadProyecto,
    PasoAprobacion,
    ProcesoAprobacion,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    SolicitudCambioModalidad,
    SolicitudCambioTutor,
    Tutor,
    TutorPrograma,
    Tutoria,
    TipoAprobacion,
)
from .aprobaciones import PLANTILLAS_PASOS
from .forms import (
    DisponibilidadTutorForm,
    ResolucionCambioTutorForm,
    ResolucionProyectoForm,
    TutoriaForm,
    RevisionPasoAprobacionForm,
)
from .modalidades import modalidades_disponibles, obtener_regla_modalidad
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
            TutorPrograma: "tutores_programas",
            DisponibilidadTutor: "disponibilidades_tutor",
            SolicitudCambioTutor: "solicitudes_cambio_tutor",
            Tutoria: "tutorias",
            AsistenciaTutoria: "asistencias_tutoria",
            ReprogramacionTutoria: "reprogramaciones_tutoria",
            ArchivoProyecto: "archivos_proyecto",
            Grabacion: "grabaciones",
            Articulo: "articulos",
            SolicitudCambioTema: "solicitudes_cambio_tema",
            SolicitudCambioModalidad: "solicitudes_cambio_modalidad",
            ConfiguracionModalidadPrograma: "configuraciones_modalidad_programa",
            ProcesoAprobacion: "procesos_aprobacion",
            PasoAprobacion: "pasos_aprobacion",
            DocumentoProcesoAprobacion: "documentos_proceso_aprobacion",
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
        self.assertIn(
            "cambio_modalidad",
            {valor for valor, _ in TipoAprobacion.choices},
        )
        self.assertIsInstance(
            ConfiguracionModalidadPrograma._meta.get_field("programa"),
            OneToOneField,
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
            "cambio_tutor_create": ({"proyecto_pk": 7}, "/titulacion/proyectos/7/cambio-tutor/"),
            "cambio_tutor_resolver": ({"pk": 8}, "/titulacion/cambios-tutor/8/resolver/"),
            "tutor_disponibilidad_create": ({"pk": 7}, "/titulacion/tutores/7/disponibilidad/crear/"),
            "calendario_tutorias": (None, "/titulacion/calendario/"),
            "tutoria_create": ({"pk": 7}, "/titulacion/proyectos/7/tutorias/programar/"),
            "tutoria_registrar": ({"pk": 8}, "/titulacion/tutorias/8/registrar/"),
            "grabacion_create": ({"pk": 8}, "/titulacion/tutorias/8/grabaciones/registrar/"),
            "articulo_edit": ({"proyecto_pk": 7}, "/titulacion/proyectos/7/articulo/editar/"),
            "cambio_tema_create": ({"proyecto_pk": 7}, "/titulacion/proyectos/7/cambio-tema/"),
            "cambio_modalidad_create": ({"proyecto_pk": 7}, "/titulacion/proyectos/7/cambio-modalidad/"),
            "cambio_modalidad_resolver": ({"pk": 7}, "/titulacion/cambios-modalidad/7/resolver/"),
            "modalidades_configuracion": (None, "/titulacion/modalidades/configuracion/"),
            "proceso_aprobacion_detail": ({"pk": 7}, "/titulacion/aprobaciones/procesos/7/"),
            "paso_aprobacion_resolver": ({"pk": 8}, "/titulacion/aprobaciones/pasos/8/resolver/"),
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


class MotorModalidadesTests(SimpleTestCase):
    def test_modalidades_estandar_tienen_producto_y_evidencias_propias(self):
        articulo = obtener_regla_modalidad(None, ModalidadProyecto.ARTICULO)
        investigacion = obtener_regla_modalidad(None, ModalidadProyecto.INVESTIGACION)
        examen = obtener_regla_modalidad(None, ModalidadProyecto.EXAMEN)

        self.assertTrue(articulo["requiere_articulo"])
        self.assertTrue(articulo["requiere_envio_revista"])
        self.assertFalse(investigacion["requiere_articulo"])
        self.assertEqual(investigacion["tipo_archivo_final"], "pdf")
        self.assertIn("documento_final", investigacion["tipos_evidencia"])
        self.assertEqual(examen["tipo_archivo_final"], "resolucion")
        self.assertIn("acta_resultado", examen["tipos_evidencia"])

    @patch("apps.titulacion.modalidades._configuracion_otra")
    def test_otra_solo_aparece_si_el_programa_la_habilita(self, configuracion):
        programa = SimpleNamespace(pk=9)
        configuracion.return_value = None
        self.assertNotIn(
            ModalidadProyecto.OTRA,
            {codigo for codigo, _ in modalidades_disponibles(programa)},
        )

        configuracion.return_value = SimpleNamespace(nombre="Proyecto aplicado")
        self.assertIn(
            (ModalidadProyecto.OTRA, "Proyecto aplicado"),
            modalidades_disponibles(programa),
        )

    def test_plantillas_de_modalidad_compilan(self):
        for nombre in (
            "titulacion/proyecto_detail.html",
            "titulacion/modalidades_configuracion.html",
            "seguimiento/dashboard.html",
            "seguimiento/checklist_cierre.html",
            "titulacion/aprobaciones.html",
            "titulacion/proceso_aprobacion_detail.html",
            "titulacion/calendario_tutorias.html",
            "titulacion/cambio_tutor_form.html",
            "titulacion/cambio_tutor_resolver.html",
            "titulacion/reprogramacion_resolver.html",
        ):
            with self.subTest(plantilla=nombre):
                self.assertIsNotNone(get_template(nombre))


class AprobacionFormalContractTests(SimpleTestCase):
    def test_proyecto_se_revisa_por_coordinacion_y_finaliza_supervision(self):
        pasos = PLANTILLAS_PASOS["proyecto"]
        self.assertEqual(len(pasos), 3)
        self.assertEqual(
            [paso["rol_responsable"] for paso in pasos],
            ["coordinador", "coordinador", "supervisor"],
        )
        self.assertEqual(pasos[-1]["codigo"], "aprobacion_supervisor")

    def test_cambios_conservan_cuatro_instancias_de_decision(self):
        for tipo in ("cambio_tema", "cambio_modalidad"):
            with self.subTest(tipo=tipo):
                pasos = PLANTILLAS_PASOS[tipo]
                self.assertEqual(len(pasos), 4)
                self.assertEqual(pasos[0]["rol_responsable"], "coordinador")
                self.assertEqual(pasos[-1]["rol_responsable"], "supervisor")

    def test_observar_solo_se_ofrece_en_revision_de_proyecto(self):
        con_observacion = RevisionPasoAprobacionForm(permite_observar=True)
        sin_observacion = RevisionPasoAprobacionForm(permite_observar=False)
        self.assertIn(
            "observar",
            {codigo for codigo, _ in con_observacion.fields["decision"].choices},
        )
        self.assertNotIn(
            "observar",
            {codigo for codigo, _ in sin_observacion.fields["decision"].choices},
        )

    def test_resolucion_exige_numero_fecha_y_pdf_si_no_existe(self):
        formulario = ResolucionProyectoForm(instance=ProyectoTitulacion())
        self.assertTrue(formulario.fields["numero_resolucion"].required)
        self.assertTrue(formulario.fields["fecha_aprobacion"].required)
        self.assertTrue(formulario.fields["documento_resolucion"].required)


class TutoresAgendaContractTests(SimpleTestCase):
    def test_programacion_solo_ofrece_los_ocho_numeros_faltantes(self):
        class TutoríasFalsas:
            def values_list(self, *args, **kwargs):
                return [1, 3, 8]

        proyecto = SimpleNamespace(tutorias=TutoríasFalsas())
        formulario = TutoriaForm(proyecto=proyecto)
        disponibles = {
            valor for valor, _ in formulario.fields["numero_tutoria"].choices
        }
        self.assertEqual(disponibles, {2, 4, 5, 6, 7})

    def test_tutoria_exige_fecha_futura_y_enlace_https(self):
        formulario = TutoriaForm(
            data={
                "numero_tutoria": 1,
                "fecha": timezone.localdate() - timedelta(days=1),
                "hora_inicio": "10:00",
                "hora_fin": "11:00",
                "enlace_virtual": "http://sala.example.test",
            }
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("fecha", formulario.errors)
        self.assertIn("enlace_virtual", formulario.errors)

    def test_disponibilidad_rechaza_bloque_invertido(self):
        formulario = DisponibilidadTutorForm(
            data={"dia_semana": 0, "hora_inicio": "12:00", "hora_fin": "11:00"}
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("hora_fin", formulario.errors)

    def test_rechazo_de_cambio_tutor_exige_explicacion(self):
        formulario = ResolucionCambioTutorForm(
            data={"decision": "rechazar", "observaciones": ""}
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn("observaciones", formulario.errors)


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
