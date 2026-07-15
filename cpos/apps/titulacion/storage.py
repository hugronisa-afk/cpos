"""Almacenamiento privado de archivos del módulo de Titulación.

No depende de ``settings.py``. Usa Supabase Storage cuando existen
``SUPABASE_URL`` y una clave secreta de servidor; de lo contrario conserva los
archivos en ``media/titulacion`` y siempre los entrega mediante una vista con
autorización de proyecto.
"""

from __future__ import annotations

import http.client
import json
import mimetypes
import os
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urljoin, urlparse

from decouple import AutoConfig
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect


BUCKET = "titulacion-privado"
MAX_DOCUMENTO = 20 * 1024 * 1024
MAX_GRABACION = 500 * 1024 * 1024
MIME_EXTENSION = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    "mp4": {"video/mp4", "audio/mp4", "application/octet-stream"},
    "webm": {"video/webm", "audio/webm", "application/octet-stream"},
    "mp3": {"audio/mpeg", "application/octet-stream"},
}


class ErrorAlmacenamiento(Exception):
    pass


def _configuracion():
    config = AutoConfig(search_path=str(settings.BASE_DIR))
    url = str(config("SUPABASE_URL", default=os.getenv("SUPABASE_URL", ""))).rstrip("/")
    clave_nueva = str(
        config(
            "SUPABASE_SECRET_KEY",
            default=os.getenv("SUPABASE_SECRET_KEY", ""),
        )
    ).strip()
    clave_legacy = str(
        config(
            "SUPABASE_SERVICE_ROLE_KEY",
            default=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )
    ).strip()
    clave = clave_nueva or clave_legacy
    preferido = str(
        config(
            "TITULACION_STORAGE_BACKEND",
            default=os.getenv("TITULACION_STORAGE_BACKEND", "auto"),
        )
    ).strip().lower()
    usar_supabase = preferido == "supabase" or (
        preferido == "auto" and bool(url and clave)
    )
    if usar_supabase and not (url and clave):
        raise ErrorAlmacenamiento(
            "Faltan SUPABASE_URL y SUPABASE_SECRET_KEY (o la clave legacy service_role)."
        )
    return url, clave, usar_supabase


def backend_activo() -> str:
    return "supabase" if _configuracion()[2] else "local"


def validar_archivo_subido(archivo, extensiones, limite_bytes):
    nombre = Path(archivo.name or "").name
    extension = Path(nombre).suffix.lower().lstrip(".")
    if extension not in set(extensiones):
        raise ValidationError(
            f"Extensión no permitida. Use: {', '.join(sorted(extensiones))}."
        )
    if archivo.size <= 0:
        raise ValidationError("El archivo está vacío.")
    if archivo.size > limite_bytes:
        raise ValidationError(
            f"El archivo supera el límite de {limite_bytes // (1024 * 1024)} MB."
        )
    mime = str(getattr(archivo, "content_type", "") or "application/octet-stream")
    if mime not in MIME_EXTENSION.get(extension, {mime}):
        raise ValidationError("El tipo de contenido no coincide con la extensión.")

    posicion = archivo.tell() if hasattr(archivo, "tell") else 0
    cabecera = archivo.read(12)
    archivo.seek(posicion)
    firmas_validas = {
        "pdf": cabecera.startswith(b"%PDF-"),
        "doc": cabecera.startswith(bytes.fromhex("D0CF11E0A1B11AE1")),
        "docx": cabecera.startswith(b"PK"),
        "mp4": len(cabecera) >= 8 and cabecera[4:8] == b"ftyp",
        "webm": cabecera.startswith(bytes.fromhex("1A45DFA3")),
        "mp3": cabecera.startswith(b"ID3") or cabecera[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"},
    }
    if extension in firmas_validas and not firmas_validas[extension]:
        raise ValidationError("La firma interna del archivo no coincide con su extensión.")
    if extension == "docx":
        try:
            archivo.seek(0)
            with zipfile.ZipFile(archivo) as contenido:
                nombres = set(contenido.namelist())
            if "[Content_Types].xml" not in nombres or "word/document.xml" not in nombres:
                raise ValidationError("El archivo no contiene un documento Word válido.")
        except zipfile.BadZipFile as error:
            raise ValidationError("El archivo DOCX está dañado.") from error
        finally:
            archivo.seek(posicion)
    return extension, mime


def _ruta_objeto(categoria, proyecto_id, extension):
    categoria_limpia = "".join(
        caracter for caracter in str(categoria).lower() if caracter.isalnum() or caracter in "-_"
    )
    return str(
        PurePosixPath(categoria_limpia)
        / str(int(proyecto_id))
        / f"{uuid.uuid4().hex}.{extension}"
    )


def _conexion_supabase(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ErrorAlmacenamiento("SUPABASE_URL debe ser una URL HTTPS válida.")
    return parsed, http.client.HTTPSConnection(parsed.netloc, timeout=120)


def _cabeceras_clave(clave):
    cabeceras = {"apikey": clave}
    if not clave.startswith("sb_secret_"):
        cabeceras["Authorization"] = f"Bearer {clave}"
    return cabeceras


def _subir_supabase(url, clave, ruta, archivo, mime):
    parsed, conexion = _conexion_supabase(url)
    endpoint = f"{parsed.path.rstrip('/')}/storage/v1/object/{quote(BUCKET)}/{quote(ruta, safe='/')}"
    conexion.putrequest("POST", endpoint)
    for nombre, valor in _cabeceras_clave(clave).items():
        conexion.putheader(nombre, valor)
    conexion.putheader("Content-Type", mime)
    conexion.putheader("Content-Length", str(archivo.size))
    conexion.putheader("x-upsert", "false")
    conexion.endheaders()
    archivo.seek(0)
    for bloque in archivo.chunks():
        conexion.send(bloque)
    respuesta = conexion.getresponse()
    cuerpo = respuesta.read()
    conexion.close()
    if respuesta.status not in {200, 201}:
        detalle = cuerpo.decode("utf-8", errors="replace")[:300]
        raise ErrorAlmacenamiento(f"Supabase Storage rechazó la carga: {detalle}")


def _subir_local(ruta, archivo):
    destino = (Path(settings.BASE_DIR) / "media" / "titulacion" / Path(ruta)).resolve()
    raiz = (Path(settings.BASE_DIR) / "media" / "titulacion").resolve()
    if raiz not in destino.parents:
        raise ErrorAlmacenamiento("Ruta de almacenamiento inválida.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    archivo.seek(0)
    with destino.open("xb") as salida:
        for bloque in archivo.chunks():
            salida.write(bloque)


def guardar_archivo(archivo, *, categoria, proyecto_id, extensiones, limite_bytes):
    extension, mime = validar_archivo_subido(archivo, extensiones, limite_bytes)
    ruta = _ruta_objeto(categoria, proyecto_id, extension)
    url, clave, usar_supabase = _configuracion()
    if usar_supabase:
        _subir_supabase(url, clave, ruta, archivo, mime)
        referencia = f"supabase:{ruta}"
    else:
        _subir_local(ruta, archivo)
        referencia = f"local:{ruta}"
    return {
        "referencia": referencia,
        "nombre_original": Path(archivo.name).name,
        "extension": extension,
        "tamano_bytes": archivo.size,
        "mime": mime,
    }


def eliminar_archivo(referencia):
    referencia = str(referencia or "")
    if referencia.startswith("local:"):
        ruta = referencia.removeprefix("local:")
        destino = (Path(settings.BASE_DIR) / "media" / "titulacion" / Path(ruta)).resolve()
        raiz = (Path(settings.BASE_DIR) / "media" / "titulacion").resolve()
        if raiz in destino.parents:
            destino.unlink(missing_ok=True)
        return
    if referencia.startswith("supabase:"):
        url, clave, _ = _configuracion()
        ruta = referencia.removeprefix("supabase:")
        parsed, conexion = _conexion_supabase(url)
        endpoint = f"{parsed.path.rstrip('/')}/storage/v1/object/{quote(BUCKET)}/{quote(ruta, safe='/')}"
        conexion.request(
            "DELETE",
            endpoint,
            headers=_cabeceras_clave(clave),
        )
        respuesta = conexion.getresponse()
        respuesta.read()
        conexion.close()


def _url_firmada_supabase(ruta, segundos=60):
    url, clave, _ = _configuracion()
    parsed, conexion = _conexion_supabase(url)
    endpoint = f"{parsed.path.rstrip('/')}/storage/v1/object/sign/{quote(BUCKET)}/{quote(ruta, safe='/')}"
    cuerpo = json.dumps({"expiresIn": segundos}).encode("utf-8")
    conexion.request(
        "POST",
        endpoint,
        body=cuerpo,
        headers={
            **_cabeceras_clave(clave),
            "Content-Type": "application/json",
            "Content-Length": str(len(cuerpo)),
        },
    )
    respuesta = conexion.getresponse()
    datos_crudos = respuesta.read()
    conexion.close()
    if respuesta.status not in {200, 201}:
        raise Http404("No fue posible generar el enlace privado.")
    datos = json.loads(datos_crudos.decode("utf-8"))
    firmada = datos.get("signedURL") or datos.get("signedUrl")
    if not firmada:
        raise Http404("Supabase no devolvió un enlace firmado.")
    if firmada.startswith(("https://", "http://")):
        return firmada
    if firmada.startswith("/storage/v1/"):
        return urljoin(f"{url}/", firmada.lstrip("/"))
    return f"{url}/storage/v1/{firmada.lstrip('/')}"


def respuesta_descarga(referencia, nombre_descarga):
    referencia = str(referencia or "")
    nombre = Path(nombre_descarga or "archivo").name
    if referencia.startswith("supabase:"):
        return redirect(_url_firmada_supabase(referencia.removeprefix("supabase:")))
    if referencia.startswith("local:"):
        ruta = referencia.removeprefix("local:")
        destino = (Path(settings.BASE_DIR) / "media" / "titulacion" / Path(ruta)).resolve()
        raiz = (Path(settings.BASE_DIR) / "media" / "titulacion").resolve()
        if raiz not in destino.parents or not destino.is_file():
            raise Http404("El archivo no está disponible.")
        tipo, _ = mimetypes.guess_type(nombre)
        return FileResponse(
            destino.open("rb"),
            as_attachment=True,
            filename=nombre,
            content_type=tipo or "application/octet-stream",
        )
    raise Http404("La referencia pertenece a un almacenamiento no administrado.")
