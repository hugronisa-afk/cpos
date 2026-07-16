import io
import zipfile
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse

from .importacion import leer_archivo_usuarios
from .models import EstadoUsuario, NivelAutoridad, Rol, UsuarioCPOS
from .services import (
    MAX_ADMINISTRADORES_DESARROLLADORES,
    obtener_sigla_rol,
    validar_asignacion_rol_tecnico,
)


class RolTecnicoTests(SimpleTestCase):
    def _usuario(self, rol_nombre):
        rol = Rol(
            id=1,
            nombre=rol_nombre,
            nivel_autoridad=NivelAutoridad.SUPERVISION,
            esta_activo=True,
        )
        return UsuarioCPOS(
            id=1,
            rol=rol,
            nombres="Persona",
            apellidos="Técnica",
            cedula="1200000000",
            correo="persona@utb.edu.ec",
            estado=EstadoUsuario.ACTIVO,
            nombre_usuario="1200000000-ADM",
        )

    def test_sigla_tecnica(self):
        self.assertEqual(obtener_sigla_rol("administrador_desarrollador"), "ADM")

    @patch("apps.accounts.services.UsuarioCPOS.objects.filter")
    def test_supervisor_puede_crear_solo_la_primera_cuenta(self, filtrar):
        consulta = MagicMock()
        consulta.exists.return_value = False
        consulta.count.return_value = 0
        filtrar.return_value = consulta
        validar_asignacion_rol_tecnico(
            actor=self._usuario("supervisor"),
            rol=Rol(nombre="administrador_desarrollador", esta_activo=True),
            estado=EstadoUsuario.ACTIVO,
        )

    @patch("apps.accounts.services.UsuarioCPOS.objects.filter")
    def test_impide_una_cuarta_cuenta_tecnica_activa(self, filtrar):
        consulta = MagicMock()
        consulta.count.return_value = MAX_ADMINISTRADORES_DESARROLLADORES
        filtrar.return_value = consulta
        with self.assertRaises(ValidationError):
            validar_asignacion_rol_tecnico(
                actor=self._usuario("administrador_desarrollador"),
                rol=Rol(nombre="administrador_desarrollador", esta_activo=True),
                estado=EstadoUsuario.ACTIVO,
            )


class LecturaImportacionTests(SimpleTestCase):
    def test_lee_csv_con_columnas_institucionales(self):
        contenido = (
            "nombres,apellidos,cedula,correo,rol\n"
            "Ana,Pérez,1200000010,ana@utb.edu.ec,tutor\n"
        ).encode("utf-8")
        archivo = SimpleUploadedFile("usuarios.csv", contenido, content_type="text/csv")
        filas = leer_archivo_usuarios(archivo)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["linea"], 2)
        self.assertEqual(filas[0]["datos"]["correo"], "ana@utb.edu.ec")

    def test_lee_primera_hoja_xlsx_sin_dependencias_externas(self):
        hoja = """<?xml version="1.0" encoding="UTF-8"?>
        <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
          <sheetData>
            <row r="1"><c r="A1" t="inlineStr"><is><t>nombres</t></is></c><c r="B1" t="inlineStr"><is><t>apellidos</t></is></c><c r="C1" t="inlineStr"><is><t>cedula</t></is></c><c r="D1" t="inlineStr"><is><t>correo</t></is></c><c r="E1" t="inlineStr"><is><t>rol</t></is></c></row>
            <row r="2"><c r="A2" t="inlineStr"><is><t>Ana</t></is></c><c r="B2" t="inlineStr"><is><t>Pérez</t></is></c><c r="C2" t="inlineStr"><is><t>1200000010</t></is></c><c r="D2" t="inlineStr"><is><t>ana@utb.edu.ec</t></is></c><c r="E2" t="inlineStr"><is><t>tutor</t></is></c></row>
          </sheetData>
        </worksheet>"""
        contenido = io.BytesIO()
        with zipfile.ZipFile(contenido, "w") as libro:
            libro.writestr("xl/worksheets/sheet1.xml", hoja)
        archivo = SimpleUploadedFile(
            "usuarios.xlsx",
            contenido.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filas = leer_archivo_usuarios(archivo)
        self.assertEqual(filas[0]["datos"]["rol"], "tutor")


class RutasFaseDosTests(SimpleTestCase):
    def test_rutas_tecnicas(self):
        self.assertEqual(reverse("accounts:importar_usuarios"), "/usuarios/importar/")
        self.assertEqual(reverse("accounts:mantenimiento"), "/mantenimiento/")
        self.assertEqual(
            reverse("accounts:plantilla_importacion_usuarios"),
            "/usuarios/importar/plantilla/",
        )
