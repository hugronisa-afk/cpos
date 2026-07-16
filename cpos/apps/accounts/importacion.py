"""Importación segura y auditable de cuentas institucionales."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from pathlib import PurePath
from xml.etree import ElementTree

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from .models import (
    Cohorte,
    EstadoCohorte,
    EstadoPrograma,
    EstadoTitulacion,
    EstadoUsuario,
    Maestrante,
    Programa,
    Rol,
    UsuarioCPOS,
)
from .services import (
    ROL_ADMIN_DESARROLLADOR,
    SIGLAS_ROL,
    crear_usuario_seguro,
    registrar_bitacora,
)


MAX_FILAS_IMPORTACION = 1000
ROLES_IMPORTABLES = {"maestrante", "tutor", "coordinador", "supervisor"}
COLUMNAS_PLANTILLA = (
    "nombres",
    "apellidos",
    "cedula",
    "correo",
    "telefono",
    "rol",
    "estado",
    "programa_codigo",
    "cohorte",
    "codigo_matricula",
)
COLUMNAS_OBLIGATORIAS = {"nombres", "apellidos", "cedula", "correo", "rol"}
ALIAS_COLUMNAS = {
    "programa": "programa_codigo",
    "codigo_programa": "programa_codigo",
    "nombre_cohorte": "cohorte",
    "matricula": "codigo_matricula",
    "codigo_de_matricula": "codigo_matricula",
    "e_mail": "correo",
    "email": "correo",
}


def _normalizar_texto(valor) -> str:
    return str(valor or "").strip()


def _normalizar_cabecera(valor) -> str:
    texto = unicodedata.normalize("NFKD", _normalizar_texto(valor))
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto.lower()).strip("_")
    return ALIAS_COLUMNAS.get(texto, texto)


def _indice_columna(referencia: str) -> int:
    letras = re.match(r"[A-Z]+", referencia or "")
    if not letras:
        return 0
    indice = 0
    for letra in letras.group(0):
        indice = indice * 26 + ord(letra) - 64
    return indice - 1


def _leer_csv(archivo) -> list[list[str]]:
    contenido = archivo.read()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    muestra = texto[:4096]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    return [list(fila) for fila in csv.reader(io.StringIO(texto), dialecto)]


def _leer_xlsx(archivo) -> list[list[str]]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        with zipfile.ZipFile(archivo) as libro:
            if sum(entrada.file_size for entrada in libro.infolist()) > 10 * 1024 * 1024:
                raise ValidationError("El contenido descomprimido del XLSX es demasiado grande.")
            compartidos = []
            if "xl/sharedStrings.xml" in libro.namelist():
                raiz = ElementTree.fromstring(libro.read("xl/sharedStrings.xml"))
                compartidos = [
                    "".join(nodo.text or "" for nodo in elemento.findall(".//x:t", namespace))
                    for elemento in raiz.findall("x:si", namespace)
                ]
            hojas = sorted(
                nombre
                for nombre in libro.namelist()
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", nombre)
            )
            if not hojas:
                raise ValidationError("El archivo XLSX no contiene hojas legibles.")
            raiz = ElementTree.fromstring(libro.read(hojas[0]))
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as error:
        raise ValidationError("El archivo XLSX está dañado o no es válido.") from error

    filas = []
    for nodo_fila in raiz.findall(".//x:sheetData/x:row", namespace):
        valores = {}
        ultimo_indice = -1
        for celda in nodo_fila.findall("x:c", namespace):
            indice = _indice_columna(celda.attrib.get("r", ""))
            ultimo_indice = max(ultimo_indice, indice)
            tipo = celda.attrib.get("t")
            if tipo == "inlineStr":
                valor = "".join(
                    nodo.text or "" for nodo in celda.findall(".//x:t", namespace)
                )
            else:
                nodo_valor = celda.find("x:v", namespace)
                valor = nodo_valor.text if nodo_valor is not None else ""
                if tipo == "s" and valor:
                    try:
                        valor = compartidos[int(valor)]
                    except (IndexError, ValueError):
                        valor = ""
            valores[indice] = valor
        filas.append([valores.get(i, "") for i in range(ultimo_indice + 1)])
    return filas


def leer_archivo_usuarios(archivo) -> list[dict]:
    extension = PurePath(str(archivo.name or "")).suffix.lower()
    filas = _leer_csv(archivo) if extension == ".csv" else _leer_xlsx(archivo)
    filas = [fila for fila in filas if any(_normalizar_texto(valor) for valor in fila)]
    if not filas:
        raise ValidationError("El archivo está vacío.")
    if len(filas) - 1 > MAX_FILAS_IMPORTACION:
        raise ValidationError(f"El archivo supera el límite de {MAX_FILAS_IMPORTACION} filas.")

    cabeceras = [_normalizar_cabecera(valor) for valor in filas[0]]
    if len(cabeceras) != len(set(cabeceras)):
        raise ValidationError("El archivo contiene columnas repetidas.")
    faltantes = sorted(COLUMNAS_OBLIGATORIAS - set(cabeceras))
    if faltantes:
        raise ValidationError("Faltan columnas obligatorias: " + ", ".join(faltantes) + ".")
    desconocidas = sorted(set(cabeceras) - set(COLUMNAS_PLANTILLA))
    if desconocidas:
        raise ValidationError("Existen columnas no reconocidas: " + ", ".join(desconocidas) + ".")

    resultado = []
    for numero, valores in enumerate(filas[1:], start=2):
        datos = {
            cabecera: _normalizar_texto(valores[indice] if indice < len(valores) else "")
            for indice, cabecera in enumerate(cabeceras)
        }
        resultado.append({"linea": numero, "datos": datos})
    return resultado


def _mensajes_error(error) -> list[str]:
    if isinstance(error, ValidationError):
        if hasattr(error, "message_dict"):
            return [
                f"{campo}: {mensaje}"
                for campo, mensajes in error.message_dict.items()
                for mensaje in mensajes
            ]
        return list(error.messages)
    return ["No fue posible procesar la fila por una restricción de datos."]


def validar_filas_usuarios(filas: list[dict]) -> list[dict]:
    roles = {
        rol.nombre.strip().lower(): rol
        for rol in Rol.objects.filter(esta_activo=True)
    }
    programas = {
        programa.codigo.strip().upper(): programa
        for programa in Programa.objects.filter(estado=EstadoPrograma.ACTIVO)
    }
    cohortes = {
        (cohorte.programa_id, cohorte.nombre.strip().lower()): cohorte
        for cohorte in Cohorte.objects.filter(estado=EstadoCohorte.ACTIVA)
    }
    correos_existentes = {
        correo.lower() for correo in UsuarioCPOS.objects.values_list("correo", flat=True)
    }
    usuarios_existentes = {
        nombre.upper()
        for nombre in UsuarioCPOS.objects.values_list("nombre_usuario", flat=True)
    }
    cedulas_roles_existentes = set(
        UsuarioCPOS.objects.values_list("cedula", "rol__nombre")
    )
    matriculas_existentes = {
        codigo.upper() for codigo in Maestrante.objects.values_list("codigo_matricula", flat=True)
    }
    correos_archivo = set()
    usuarios_archivo = set()
    cedulas_roles_archivo = set()
    matriculas_archivo = set()
    resultados = []

    for fila in filas:
        datos = {columna: _normalizar_texto(fila["datos"].get(columna)) for columna in COLUMNAS_PLANTILLA}
        datos["cedula"] = re.sub(r"[\s-]+", "", datos["cedula"])
        datos["correo"] = datos["correo"].lower()
        datos["rol"] = datos["rol"].lower()
        datos["estado"] = (datos["estado"] or EstadoUsuario.ACTIVO).lower()
        datos["programa_codigo"] = datos["programa_codigo"].upper()
        datos["codigo_matricula"] = datos["codigo_matricula"].upper()
        errores = []

        for campo in COLUMNAS_OBLIGATORIAS:
            if not datos[campo]:
                errores.append(f"{campo}: es obligatorio.")
        for campo in ("nombres", "apellidos"):
            if len(datos[campo]) > 120:
                errores.append(f"{campo}: no puede superar 120 caracteres.")
        if datos["cedula"] and (not datos["cedula"].isdigit() or len(datos["cedula"]) > 20):
            errores.append("cedula: debe contener hasta 20 dígitos.")
        if datos["correo"]:
            if len(datos["correo"]) > 180:
                errores.append("correo: no puede superar 180 caracteres.")
            try:
                validate_email(datos["correo"])
            except ValidationError:
                errores.append("correo: no tiene un formato válido.")
        if len(datos["telefono"]) > 30:
            errores.append("telefono: no puede superar 30 caracteres.")
        if len(datos["codigo_matricula"]) > 50:
            errores.append("codigo_matricula: no puede superar 50 caracteres.")
        if datos["rol"] == ROL_ADMIN_DESARROLLADOR:
            errores.append("rol: las cuentas técnicas no se crean mediante importación.")
        elif datos["rol"] not in ROLES_IMPORTABLES:
            errores.append("rol: debe ser maestrante, tutor, coordinador o supervisor.")
        rol = roles.get(datos["rol"])
        if datos["rol"] in ROLES_IMPORTABLES and not rol:
            errores.append("rol: no existe o está inactivo en el sistema.")
        if datos["estado"] not in {EstadoUsuario.ACTIVO, EstadoUsuario.INACTIVO}:
            errores.append("estado: debe ser activo o inactivo.")

        nombre_usuario = ""
        if datos["cedula"] and datos["rol"] in SIGLAS_ROL:
            nombre_usuario = f'{datos["cedula"]}-{SIGLAS_ROL[datos["rol"]]}'.upper()
        clave_cedula_rol = (datos["cedula"], datos["rol"])
        if datos["correo"] in correos_existentes:
            errores.append("correo: ya está registrado.")
        if datos["correo"] in correos_archivo:
            errores.append("correo: está repetido dentro del archivo.")
        if nombre_usuario in usuarios_existentes:
            errores.append("cedula/rol: el nombre de usuario generado ya existe.")
        if nombre_usuario in usuarios_archivo:
            errores.append("cedula/rol: está repetido dentro del archivo.")
        if clave_cedula_rol in cedulas_roles_existentes:
            errores.append("cedula/rol: esta combinación ya está registrada.")
        if clave_cedula_rol in cedulas_roles_archivo:
            errores.append("cedula/rol: está repetida dentro del archivo.")

        programa = None
        cohorte = None
        if datos["rol"] == "maestrante":
            for campo in ("programa_codigo", "cohorte", "codigo_matricula"):
                if not datos[campo]:
                    errores.append(f"{campo}: es obligatorio para maestrantes.")
            programa = programas.get(datos["programa_codigo"])
            if datos["programa_codigo"] and not programa:
                errores.append("programa_codigo: no existe o está inactivo.")
            if programa and datos["cohorte"]:
                cohorte = cohortes.get((programa.pk, datos["cohorte"].lower()))
                if not cohorte:
                    errores.append("cohorte: no existe, está inactiva o pertenece a otro programa.")
            if datos["codigo_matricula"] in matriculas_existentes:
                errores.append("codigo_matricula: ya está registrado.")
            if datos["codigo_matricula"] in matriculas_archivo:
                errores.append("codigo_matricula: está repetido dentro del archivo.")
        elif any(datos[campo] for campo in ("programa_codigo", "cohorte", "codigo_matricula")):
            errores.append("datos académicos: solo corresponden al rol maestrante.")

        if datos["correo"]:
            correos_archivo.add(datos["correo"])
        if nombre_usuario:
            usuarios_archivo.add(nombre_usuario)
        if datos["cedula"] and datos["rol"]:
            cedulas_roles_archivo.add(clave_cedula_rol)
        if datos["codigo_matricula"]:
            matriculas_archivo.add(datos["codigo_matricula"])
        resultados.append(
            {
                "linea": fila["linea"],
                "datos": datos,
                "rol_id": rol.pk if rol else None,
                "programa_id": programa.pk if programa else None,
                "cohorte_id": cohorte.pk if cohorte else None,
                "nombre_usuario": nombre_usuario,
                "errores": errores,
                "valida": not errores,
                "estado_resultado": "válida" if not errores else "error",
            }
        )
    return resultados


def procesar_importacion_usuarios(archivo, *, importar: bool, actor, request=None) -> dict:
    filas = validar_filas_usuarios(leer_archivo_usuarios(archivo))
    creadas = 0
    for fila in filas:
        if not importar or not fila["valida"]:
            continue
        datos = fila["datos"]
        try:
            with transaction.atomic():
                usuario = crear_usuario_seguro(
                    rol=fila["rol_id"],
                    nombres=datos["nombres"],
                    apellidos=datos["apellidos"],
                    cedula=datos["cedula"],
                    correo=datos["correo"],
                    telefono=datos["telefono"] or None,
                    estado=datos["estado"],
                    contrasena=None,
                    actor=actor,
                    request=request,
                )
                if datos["rol"] == "maestrante":
                    Maestrante.objects.create(
                        usuario=usuario,
                        programa_id=fila["programa_id"],
                        cohorte_id=fila["cohorte_id"],
                        codigo_matricula=datos["codigo_matricula"],
                        estado_titulacion=EstadoTitulacion.SIN_PROYECTO,
                    )
            fila["estado_resultado"] = "creada"
            fila["usuario_id"] = usuario.pk
            creadas += 1
        except (ValidationError, IntegrityError) as error:
            fila["errores"] = _mensajes_error(error)
            fila["valida"] = False
            fila["estado_resultado"] = "error"

    total = len(filas)
    errores = sum(bool(fila["errores"]) for fila in filas)
    validas = total - errores
    if importar:
        registrar_bitacora(
            usuario=actor,
            modulo="mantenimiento",
            accion="importar_usuarios",
            tabla_afectada="usuarios",
            descripcion=(
                f"Importación procesada: {total} filas, {creadas} cuentas creadas "
                f"y {errores} filas con error."
            ),
            request=request,
        )
    return {
        "modo": "importacion" if importar else "validacion",
        "total": total,
        "validas": validas,
        "creadas": creadas,
        "errores": errores,
        "filas": filas,
    }
