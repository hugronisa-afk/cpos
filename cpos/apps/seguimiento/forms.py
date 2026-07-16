from django import forms
from django.core.exceptions import ValidationError

from apps.titulacion.models import Articulo, EstadoTutoria, TipoGrabacion
from apps.titulacion.modalidades import obtener_regla_modalidad
from apps.titulacion.storage import MAX_DOCUMENTO, MAX_GRABACION, validar_archivo_subido

from .models import (
    ESTADO_VALIDACION_CHOICES,
    SECCION_ARTICULO_CHOICES,
    TIPO_EVIDENCIA_CHOICES,
)


class BaseStyledForm:
    def aplicar_estilos(self):
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault("class", "form-control")


class AsistenciaTutoriaForm(BaseStyledForm, forms.Form):
    asistio_tutor = forms.BooleanField(required=False, label="Asistió el tutor")
    asistio_maestrante = forms.BooleanField(
        required=False,
        label="Asistió el maestrante",
    )
    estado_tutoria = forms.ChoiceField(label="Estado de la tutoría", choices=())
    observaciones = forms.CharField(
        required=False,
        label="Observaciones",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    motivo_correccion = forms.CharField(
        required=False,
        label="Motivo de la corrección",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        self.es_correccion = kwargs.pop("es_correccion", False)
        self.permite_cancelar = kwargs.pop("permite_cancelar", False)
        self.solo_cancelar = kwargs.pop("solo_cancelar", False)
        super().__init__(*args, **kwargs)
        opciones = [] if self.solo_cancelar else [
            (EstadoTutoria.REALIZADA, "Realizada"),
            (EstadoTutoria.NO_REALIZADA, "No realizada"),
        ]
        if self.permite_cancelar or self.solo_cancelar:
            opciones.append((EstadoTutoria.CANCELADA, "Cancelada"))
        self.fields["estado_tutoria"].choices = opciones
        if self.es_correccion:
            self.fields["motivo_correccion"].required = True
        else:
            self.fields.pop("motivo_correccion")
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        estado = datos.get("estado_tutoria")
        asistio_tutor = bool(datos.get("asistio_tutor"))
        asistio_maestrante = bool(datos.get("asistio_maestrante"))
        if estado == EstadoTutoria.REALIZADA and not (
            asistio_tutor and asistio_maestrante
        ):
            raise ValidationError(
                "La tutoría realizada requiere asistencia del tutor y del maestrante."
            )
        if estado == EstadoTutoria.NO_REALIZADA and (
            asistio_tutor and asistio_maestrante
        ):
            raise ValidationError(
                "Si ambos participantes asistieron, la tutoría no puede quedar no realizada."
            )
        if estado in {
            EstadoTutoria.NO_REALIZADA,
            EstadoTutoria.CANCELADA,
        } and not str(datos.get("observaciones") or "").strip():
            self.add_error(
                "observaciones",
                "Explique por qué la sesión no se realizó.",
            )
        return datos


class GrabacionForm(BaseStyledForm, forms.Form):
    tipo_grabacion = forms.ChoiceField(
        label="Tipo de grabación",
        choices=TipoGrabacion.choices,
    )
    enlace_grabacion = forms.URLField(
        required=False,
        label="Enlace HTTPS",
        widget=forms.URLInput(attrs={"placeholder": "https://..."}),
    )
    archivo = forms.FileField(
        required=False,
        label="Archivo de grabación",
        help_text="MP4, WEBM o MP3 de hasta 500 MB.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_grabacion")
        enlace = str(datos.get("enlace_grabacion") or "").strip()
        archivo = datos.get("archivo")
        if tipo == TipoGrabacion.ENLACE:
            if not enlace or archivo:
                raise ValidationError("Para tipo enlace indique únicamente el enlace.")
            if not enlace.lower().startswith("https://"):
                self.add_error("enlace_grabacion", "El enlace debe usar HTTPS.")
        elif tipo == TipoGrabacion.ARCHIVO:
            if not archivo or enlace:
                raise ValidationError("Para tipo archivo adjunte únicamente el archivo.")
        if archivo:
            try:
                validar_archivo_subido(
                    archivo,
                    {"mp4", "webm", "mp3"},
                    MAX_GRABACION,
                )
            except ValidationError as error:
                self.add_error("archivo", error)
        return datos


class EvidenciaForm(BaseStyledForm, forms.Form):
    tipo_avance = forms.ChoiceField(
        label="Tipo de avance",
        choices=TIPO_EVIDENCIA_CHOICES,
    )
    titulo = forms.CharField(
        max_length=255,
        label="Título de la evidencia",
        widget=forms.TextInput(attrs={"placeholder": "Ejemplo: Avance de metodología"}),
    )
    descripcion = forms.CharField(
        required=False,
        label="Descripción",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    archivo = forms.FileField(
        label="Archivo de evidencia",
        help_text="PDF, DOC o DOCX de hasta 20 MB.",
    )

    def __init__(self, *args, **kwargs):
        self.tutoria = kwargs.pop("tutoria", None)
        self.proyecto = kwargs.pop("proyecto", None)
        super().__init__(*args, **kwargs)
        if self.proyecto:
            regla = obtener_regla_modalidad(
                self.proyecto.maestrante.programa,
                self.proyecto.modalidad,
            )
            self.fields["tipo_avance"].choices = regla["evidencias"]
            self.fields["tipo_avance"].help_text = (
                f'Tipos permitidos para {regla["nombre"]}.'
            )
        self.aplicar_estilos()

    def clean_titulo(self):
        titulo = self.cleaned_data["titulo"].strip()
        if not titulo:
            raise ValidationError("El título es obligatorio.")
        return titulo

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        validar_archivo_subido(archivo, {"pdf", "doc", "docx"}, MAX_DOCUMENTO)
        return archivo

    def clean(self):
        datos = super().clean()
        if (
            self.tutoria
            and self.proyecto
            and self.tutoria.proyecto_id != self.proyecto.pk
        ):
            raise ValidationError(
                "No puede asociar una evidencia a una tutoría de otro proyecto."
            )
        return datos


class ValidacionEvidenciaForm(BaseStyledForm, forms.Form):
    estado_resultado = forms.ChoiceField(
        label="Resultado de la revisión",
        choices=ESTADO_VALIDACION_CHOICES,
    )
    observaciones = forms.CharField(
        required=False,
        label="Observaciones del tutor",
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        if (
            datos.get("estado_resultado") in {"observada", "rechazada"}
            and not str(datos.get("observaciones") or "").strip()
        ):
            self.add_error(
                "observaciones",
                "Debe explicar por qué la evidencia fue observada o rechazada.",
            )
        return datos


class CorreccionEvidenciaForm(BaseStyledForm, forms.Form):
    archivo = forms.FileField(
        label="Archivo corregido",
        help_text="PDF, DOC o DOCX de hasta 20 MB.",
    )
    comentario = forms.CharField(
        label="Descripción de los cambios",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, **kwargs):
        self.evidencia = kwargs.pop("evidencia", None)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        validar_archivo_subido(archivo, {"pdf", "doc", "docx"}, MAX_DOCUMENTO)
        return archivo

    def clean_comentario(self):
        comentario = self.cleaned_data["comentario"].strip()
        if not comentario:
            raise ValidationError("Debe describir los cambios realizados.")
        return comentario

    def clean(self):
        datos = super().clean()
        if self.evidencia and self.evidencia.estado != "observada":
            raise ValidationError(
                "Solo se pueden corregir evidencias que estén observadas."
            )
        return datos


class ArticuloSeccionForm(BaseStyledForm, forms.Form):
    seccion = forms.ChoiceField(label="Sección", choices=SECCION_ARTICULO_CHOICES)
    contenido = forms.CharField(
        label="Contenido",
        widget=forms.Textarea(attrs={"rows": 10}),
    )

    def __init__(self, *args, **kwargs):
        self.articulo = kwargs.pop("articulo", None)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean_contenido(self):
        contenido = self.cleaned_data["contenido"].strip()
        if len(contenido) < 5:
            raise ValidationError("El contenido de la sección es demasiado corto.")
        return contenido


class EnvioRevistaForm(BaseStyledForm, forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ("fecha_envio_revista", "estado_respuesta_revista")
        labels = {
            "fecha_envio_revista": "Fecha de envío",
            "estado_respuesta_revista": "Estado de respuesta",
        }
        widgets = {
            "fecha_envio_revista": forms.DateInput(attrs={"type": "date"}),
            "estado_respuesta_revista": forms.TextInput(
                attrs={"placeholder": "Ejemplo: enviado, recibido o aceptado"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean_fecha_envio_revista(self):
        fecha = self.cleaned_data.get("fecha_envio_revista")
        if not fecha:
            raise ValidationError("Debe ingresar la fecha de envío a revista.")
        return fecha


class ChecklistCierreForm(BaseStyledForm, forms.Form):
    confirma_revision = forms.BooleanField(
        required=True,
        label="Confirmo que revisé el checklist de cierre",
    )
    observaciones = forms.CharField(
        required=False,
        label="Observaciones de cierre",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, **kwargs):
        self.puede_cerrar = kwargs.pop("puede_cerrar", False)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        if not self.puede_cerrar:
            raise ValidationError(
                "No se puede cerrar el proceso porque aún existen requisitos pendientes en el checklist."
            )
        return datos
