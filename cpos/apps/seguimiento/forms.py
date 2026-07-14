from django import forms
from django.core.exceptions import ValidationError

from .models import (
    AsistenciaTutoria,
    Grabacion,
    Evidencia,
    EvidenciaVersion,
    ValidacionEvidencia,
    Articulo,
    Aprobacion,
    ESTADO_TUTORIA_CHOICES,
    ESTADO_EVIDENCIA_CHOICES,
    TIPO_EVIDENCIA_CHOICES,
)


class BaseStyledForm:
    """
    Agrega clases CSS automáticamente para que los formularios
    se vean bien con los templates existentes.
    """

    def aplicar_estilos(self):
        for field_name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({"class": "form-check-input"})
            elif isinstance(widget, forms.Textarea):
                widget.attrs.update({
                    "class": "form-control",
                    "rows": 4,
                })
            elif isinstance(widget, forms.Select):
                widget.attrs.update({"class": "form-control"})
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs.update({"class": "form-control"})
            else:
                widget.attrs.update({"class": "form-control"})


class AsistenciaTutoriaForm(BaseStyledForm, forms.Form):
    """
    Formulario para registrar asistencia del tutor y del maestrante
    en una tutoría.
    """

    asistio_tutor = forms.BooleanField(
        required=False,
        label="Asistió el tutor"
    )

    asistio_maestrante = forms.BooleanField(
        required=False,
        label="Asistió el maestrante"
    )

    estado_tutoria = forms.ChoiceField(
        choices=ESTADO_TUTORIA_CHOICES,
        label="Estado de la tutoría"
    )

    observaciones = forms.CharField(
        required=False,
        label="Observaciones",
        widget=forms.Textarea(attrs={
            "placeholder": "Ingrese observaciones de la asistencia o desarrollo de la tutoría."
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Para asistencia normalmente no queremos permitir todos los estados.
        self.fields["estado_tutoria"].choices = [
            ("realizada", "Realizada"),
            ("no_realizada", "No realizada"),
            ("reprogramada", "Reprogramada"),
            ("cancelada", "Cancelada"),
        ]

        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()

        estado = cleaned_data.get("estado_tutoria")
        asistio_tutor = cleaned_data.get("asistio_tutor")
        asistio_maestrante = cleaned_data.get("asistio_maestrante")

        if estado == "realizada" and not asistio_tutor and not asistio_maestrante:
            raise ValidationError(
                "No puedes marcar la tutoría como realizada si no asistió ningún participante."
            )

        return cleaned_data


class GrabacionForm(BaseStyledForm, forms.ModelForm):
    """
    Formulario para registrar enlace o archivo de grabación.
    """

    class Meta:
        model = Grabacion
        fields = [
            "enlace",
            "archivo",
            "observaciones",
        ]
        labels = {
            "enlace": "Enlace de grabación",
            "archivo": "Archivo de grabación",
            "observaciones": "Observaciones",
        }
        widgets = {
            "enlace": forms.URLInput(attrs={
                "placeholder": "https://..."
            }),
            "observaciones": forms.Textarea(attrs={
                "placeholder": "Observaciones opcionales sobre la grabación."
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()
        enlace = cleaned_data.get("enlace")
        archivo = cleaned_data.get("archivo")

        if not enlace and not archivo:
            raise ValidationError(
                "Debes registrar un enlace o subir un archivo de grabación."
            )

        return cleaned_data


class EvidenciaForm(BaseStyledForm, forms.ModelForm):
    """
    Formulario para que el maestrante suba evidencia por tutoría.
    """

    class Meta:
        model = Evidencia
        fields = [
            "tipo_avance",
            "titulo",
            "descripcion",
            "archivo",
            "enlace",
        ]
        labels = {
            "tipo_avance": "Tipo de avance",
            "titulo": "Título de la evidencia",
            "descripcion": "Descripción",
            "archivo": "Archivo de evidencia",
            "enlace": "Enlace de evidencia",
        }
        widgets = {
            "tipo_avance": forms.Select(choices=TIPO_EVIDENCIA_CHOICES),
            "titulo": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Avance de metodología"
            }),
            "descripcion": forms.Textarea(attrs={
                "placeholder": "Describe brevemente qué contiene la evidencia."
            }),
            "enlace": forms.URLInput(attrs={
                "placeholder": "https://..."
            }),
        }

    def __init__(self, *args, **kwargs):
        self.tutoria = kwargs.pop("tutoria", None)
        self.proyecto = kwargs.pop("proyecto", None)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()

        archivo = cleaned_data.get("archivo")
        enlace = cleaned_data.get("enlace")

        if not archivo and not enlace:
            raise ValidationError(
                "Debes subir un archivo o registrar un enlace de evidencia."
            )

        if self.tutoria and self.proyecto:
            if self.tutoria.proyecto_id != self.proyecto.id:
                raise ValidationError(
                    "No puedes asociar evidencia a una tutoría de otro proyecto."
                )

        return cleaned_data


class ValidacionEvidenciaForm(BaseStyledForm, forms.ModelForm):
    """
    Formulario para que el tutor valide, observe o rechace evidencia.
    """

    class Meta:
        model = ValidacionEvidencia
        fields = [
            "estado",
            "observaciones",
        ]
        labels = {
            "estado": "Resultado de la revisión",
            "observaciones": "Observaciones del tutor",
        }
        widgets = {
            "estado": forms.Select(),
            "observaciones": forms.Textarea(attrs={
                "placeholder": "Ingrese observaciones si la evidencia será observada o rechazada."
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["estado"].choices = [
            ("validada", "Validada"),
            ("observada", "Observada"),
            ("rechazada", "Rechazada"),
        ]

        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()

        estado = cleaned_data.get("estado")
        observaciones = cleaned_data.get("observaciones")

        if estado in ["observada", "rechazada"] and not observaciones:
            raise ValidationError(
                "Debes ingresar observaciones cuando observes o rechaces una evidencia."
            )

        return cleaned_data


class CorreccionEvidenciaForm(BaseStyledForm, forms.ModelForm):
    """
    Formulario para que el maestrante suba una nueva versión
    de una evidencia observada.
    """

    class Meta:
        model = EvidenciaVersion
        fields = [
            "archivo",
            "enlace",
            "descripcion_cambios",
        ]
        labels = {
            "archivo": "Nuevo archivo corregido",
            "enlace": "Nuevo enlace corregido",
            "descripcion_cambios": "Descripción de cambios realizados",
        }
        widgets = {
            "enlace": forms.URLInput(attrs={
                "placeholder": "https://..."
            }),
            "descripcion_cambios": forms.Textarea(attrs={
                "placeholder": "Explica qué corregiste según las observaciones del tutor."
            }),
        }

    def __init__(self, *args, **kwargs):
        self.evidencia = kwargs.pop("evidencia", None)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()

        archivo = cleaned_data.get("archivo")
        enlace = cleaned_data.get("enlace")
        descripcion_cambios = cleaned_data.get("descripcion_cambios")

        if not archivo and not enlace:
            raise ValidationError(
                "Debes subir un archivo corregido o registrar un nuevo enlace."
            )

        if not descripcion_cambios:
            raise ValidationError(
                "Debes describir los cambios realizados."
            )

        if self.evidencia and self.evidencia.estado != "observada":
            raise ValidationError(
                "Solo se pueden corregir evidencias que estén observadas."
            )

        return cleaned_data


class ArticuloSeccionForm(BaseStyledForm, forms.Form):
    """
    Formulario para editar una sección específica del artículo.
    No usamos ModelForm directo porque se editará una sección dinámica:
    titulo, introduccion, metodologia, resultados, conclusiones o referencias.
    """

    SECCIONES = [
        ("titulo", "Título"),
        ("introduccion", "Introducción"),
        ("metodologia", "Metodología"),
        ("resultados", "Resultados"),
        ("conclusiones", "Conclusiones"),
        ("referencias", "Referencias"),
    ]

    seccion = forms.ChoiceField(
        choices=SECCIONES,
        label="Sección"
    )

    contenido = forms.CharField(
        label="Contenido",
        widget=forms.Textarea(attrs={
            "placeholder": "Escribe el contenido de la sección seleccionada.",
            "rows": 8,
        })
    )

    def __init__(self, *args, **kwargs):
        self.articulo = kwargs.pop("articulo", None)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean_contenido(self):
        contenido = self.cleaned_data.get("contenido")

        if not contenido or len(contenido.strip()) < 5:
            raise ValidationError(
                "El contenido de la sección es demasiado corto."
            )

        return contenido


class EnvioRevistaForm(BaseStyledForm, forms.ModelForm):
    """
    Formulario para registrar envío del artículo a revista.
    """

    class Meta:
        model = Articulo
        fields = [
            "revista_nombre",
            "revista_url",
            "fecha_envio_revista",
            "estado_respuesta_revista",
            "observaciones_revista",
        ]
        labels = {
            "revista_nombre": "Nombre de la revista",
            "revista_url": "URL de la revista",
            "fecha_envio_revista": "Fecha de envío",
            "estado_respuesta_revista": "Estado de respuesta",
            "observaciones_revista": "Observaciones",
        }
        widgets = {
            "revista_nombre": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Revista Científica UTB"
            }),
            "revista_url": forms.URLInput(attrs={
                "placeholder": "https://..."
            }),
            "fecha_envio_revista": forms.DateInput(attrs={
                "type": "date"
            }),
            "estado_respuesta_revista": forms.TextInput(attrs={
                "placeholder": "Ejemplo: enviado, recibido, aceptado, observado, rechazado"
            }),
            "observaciones_revista": forms.Textarea(attrs={
                "placeholder": "Observaciones del envío o respuesta de la revista."
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()

        revista_nombre = cleaned_data.get("revista_nombre")
        fecha_envio = cleaned_data.get("fecha_envio_revista")

        if not revista_nombre:
            raise ValidationError("Debes ingresar el nombre de la revista.")

        if not fecha_envio:
            raise ValidationError("Debes ingresar la fecha de envío a revista.")

        return cleaned_data


class ChecklistCierreForm(BaseStyledForm, forms.Form):
    """
    Formulario simple para confirmar revisión de cierre.
    La regla fuerte de cierre se hará en services.py:
    8 tutorías realizadas y 8 evidencias validadas.
    """

    confirma_revision = forms.BooleanField(
        required=True,
        label="Confirmo que revisé el checklist de cierre"
    )

    observaciones = forms.CharField(
        required=False,
        label="Observaciones de cierre",
        widget=forms.Textarea(attrs={
            "placeholder": "Observaciones opcionales del cierre del proceso."
        })
    )

    def __init__(self, *args, **kwargs):
        self.puede_cerrar = kwargs.pop("puede_cerrar", False)
        super().__init__(*args, **kwargs)
        self.aplicar_estilos()

    def clean(self):
        cleaned_data = super().clean()

        if not self.puede_cerrar:
            raise ValidationError(
                "No se puede cerrar el proceso porque aún no cumple con 8 tutorías realizadas y 8 evidencias validadas."
            )

        return cleaned_data