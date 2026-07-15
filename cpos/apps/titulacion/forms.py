from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.models import EstadoUsuario, UsuarioCPOS

from .models import (
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    EstadoProyecto,
    Grabacion,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTema,
    TipoArchivo,
    TipoGrabacion,
    Tutor,
    Tutoria,
)
from .storage import MAX_DOCUMENTO, MAX_GRABACION, validar_archivo_subido


class FormularioEstilizadoMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if not isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault("class", "form-control")


class UsuarioTutorChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, usuario):
        return (
            f"{usuario.nombre_completo} · {usuario.nombre_usuario} · "
            f"{usuario.correo}"
        )


class TutorForm(FormularioEstilizadoMixin, forms.ModelForm):
    usuario = UsuarioTutorChoiceField(
        queryset=UsuarioCPOS.objects.none(),
        label="Usuario tutor",
        help_text="Solo se muestran cuentas activas con rol tutor y sin perfil asociado.",
    )

    class Meta:
        model = Tutor
        fields = (
            "usuario",
            "titulo_academico",
            "especialidad",
            "linea_investigacion",
            "estado",
        )
        labels = {
            "titulo_academico": "Título académico",
            "linea_investigacion": "Línea de investigación",
        }
        widgets = {
            "titulo_academico": forms.TextInput(
                attrs={"placeholder": "Ejemplo: PhD. en Ciencias de la Computación"}
            ),
            "especialidad": forms.TextInput(
                attrs={"placeholder": "Ejemplo: Ingeniería de software"}
            ),
            "linea_investigacion": forms.TextInput(
                attrs={"placeholder": "Ejemplo: Sistemas inteligentes y educación"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuarios = UsuarioCPOS.objects.select_related("rol").filter(
            rol__nombre__iexact="tutor",
            rol__esta_activo=True,
            estado=EstadoUsuario.ACTIVO,
        )
        if self.instance and self.instance.pk:
            usuarios = usuarios.filter(
                Q(perfil_tutor__isnull=True) | Q(pk=self.instance.usuario_id)
            )
            self.fields["usuario"].disabled = True
            self.fields["usuario"].help_text = (
                "El usuario asociado no puede cambiarse después del registro."
            )
        else:
            usuarios = usuarios.filter(perfil_tutor__isnull=True)
        self.fields["usuario"].queryset = usuarios.order_by(
            "apellidos", "nombres", "nombre_usuario"
        )

    def clean_usuario(self):
        usuario = self.cleaned_data["usuario"]
        if usuario.rol.nombre.strip().lower() != "tutor":
            raise ValidationError("El usuario seleccionado no tiene el rol tutor.")
        if not usuario.is_active or not usuario.rol.esta_activo:
            raise ValidationError("La cuenta del tutor debe estar activa.")

        existente = Tutor.objects.filter(usuario=usuario)
        if self.instance and self.instance.pk:
            existente = existente.exclude(pk=self.instance.pk)
        if existente.exists():
            raise ValidationError("Este usuario ya tiene un perfil de tutor.")
        return usuario

    def clean(self):
        datos = super().clean()
        for campo in ("titulo_academico", "especialidad", "linea_investigacion"):
            valor = datos.get(campo)
            datos[campo] = valor.strip() if valor else None
        return datos


class ProyectoForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = ProyectoTitulacion
        fields = ("tema", "modalidad")
        labels = {"tema": "Tema de titulación", "modalidad": "Modalidad"}
        widgets = {"tema": forms.Textarea(attrs={"rows": 4})}

    def clean_tema(self):
        tema = self.cleaned_data["tema"].strip()
        if not tema:
            raise ValidationError("El tema es obligatorio.")
        return tema


class RevisionProyectoForm(FormularioEstilizadoMixin, forms.Form):
    estado = forms.ChoiceField(
        choices=(
            (EstadoProyecto.OBSERVADO, "Observar y devolver"),
            (EstadoProyecto.RECHAZADO, "Rechazar"),
            (EstadoProyecto.APROBADO, "Aprobar"),
        )
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, puede_aprobar=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not puede_aprobar:
            self.fields["estado"].choices = tuple(
                opcion
                for opcion in self.fields["estado"].choices
                if opcion[0] != EstadoProyecto.APROBADO
            )


class ResolucionProyectoForm(FormularioEstilizadoMixin, forms.ModelForm):
    documento_resolucion = forms.FileField(
        required=False,
        label="Documento de resolución",
        help_text="PDF de hasta 20 MB.",
    )

    class Meta:
        model = ProyectoTitulacion
        fields = ("numero_resolucion", "fecha_aprobacion")
        labels = {
            "numero_resolucion": "Número de resolución",
            "fecha_aprobacion": "Fecha de aprobación",
        }
        widgets = {"fecha_aprobacion": forms.DateInput(attrs={"type": "date"})}

    def clean_documento_resolucion(self):
        archivo = self.cleaned_data.get("documento_resolucion")
        if archivo:
            validar_archivo_subido(archivo, {"pdf"}, MAX_DOCUMENTO)
        return archivo


class AsignacionTutorForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = AsignacionTutor
        fields = ("tutor", "motivo_cambio")
        labels = {"motivo_cambio": "Motivo del cambio (si reemplaza al tutor actual)"}
        widgets = {"motivo_cambio": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tutor"].queryset = Tutor.objects.select_related("usuario").filter(
            estado="disponible", usuario__estado="activo", usuario__rol__esta_activo=True
        )


class TutoriaForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = Tutoria
        fields = (
            "numero_tutoria",
            "fecha",
            "hora_inicio",
            "hora_fin",
            "enlace_virtual",
        )
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }


class RegistroTutoriaForm(FormularioEstilizadoMixin, forms.Form):
    estado = forms.ChoiceField(
        choices=(("realizada", "Realizada"), ("no_realizada", "No realizada"), ("cancelada", "Cancelada"))
    )
    asistio_tutor = forms.BooleanField(required=False)
    asistio_maestrante = forms.BooleanField(required=False)
    observacion_general = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    observaciones_asistencia = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ReprogramacionTutoriaForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = ReprogramacionTutoria
        fields = ("fecha_nueva", "hora_inicio_nueva", "hora_fin_nueva", "motivo")
        widgets = {
            "fecha_nueva": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio_nueva": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin_nueva": forms.TimeInput(attrs={"type": "time"}),
            "motivo": forms.Textarea(attrs={"rows": 3}),
        }


class ArchivoProyectoForm(FormularioEstilizadoMixin, forms.Form):
    tipo_archivo = forms.ChoiceField(choices=TipoArchivo.choices)
    archivo = forms.FileField(
        help_text="PDF, DOC o DOCX de hasta 20 MB, según el tipo seleccionado."
    )

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_archivo")
        archivo = datos.get("archivo")
        permitidas = {
            TipoArchivo.WORD: {"doc", "docx"},
            TipoArchivo.PDF: {"pdf"},
            TipoArchivo.RESOLUCION: {"pdf"},
            TipoArchivo.ANEXO: {"doc", "docx", "pdf"},
        }
        if tipo and archivo:
            try:
                validar_archivo_subido(archivo, permitidas[tipo], MAX_DOCUMENTO)
            except ValidationError as error:
                self.add_error("archivo", error)
        return datos


class GrabacionForm(FormularioEstilizadoMixin, forms.Form):
    tipo_grabacion = forms.ChoiceField(choices=TipoGrabacion.choices)
    enlace_grabacion = forms.URLField(required=False, label="Enlace HTTPS")
    archivo = forms.FileField(
        required=False,
        help_text="MP4, WEBM o MP3 de hasta 500 MB.",
    )

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_grabacion")
        enlace = (datos.get("enlace_grabacion") or "").strip()
        archivo = datos.get("archivo")
        if tipo == TipoGrabacion.ENLACE and (not enlace or archivo):
            raise ValidationError("Para tipo enlace, indique únicamente el enlace.")
        if tipo == TipoGrabacion.ARCHIVO and (not archivo or enlace):
            raise ValidationError("Para tipo archivo, adjunte únicamente el archivo.")
        if enlace and not enlace.lower().startswith("https://"):
            self.add_error("enlace_grabacion", "El enlace debe usar HTTPS.")
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


class RevisionArchivoForm(FormularioEstilizadoMixin, forms.Form):
    estado = forms.ChoiceField(
        choices=(
            ("aprobado", "Aprobar"),
            ("observado", "Observar y solicitar corrección"),
            ("rechazado", "Rechazar"),
        )
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def clean(self):
        datos = super().clean()
        if datos.get("estado") != "aprobado" and not str(
            datos.get("observaciones") or ""
        ).strip():
            self.add_error("observaciones", "Debe explicar la observación o rechazo.")
        return datos


class ArticuloForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = Articulo
        fields = (
            "titulo",
            "introduccion",
            "metodologia",
            "resultados",
            "conclusiones",
            "referencias",
            "porcentaje_avance",
        )
        widgets = {
            campo: forms.Textarea(attrs={"rows": 5})
            for campo in ("introduccion", "metodologia", "resultados", "conclusiones", "referencias")
        }


class RevisionArticuloForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ("estado", "porcentaje_avance")


class SolicitudCambioTemaForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = SolicitudCambioTema
        fields = ("tema_propuesto", "justificacion")
        widgets = {
            "tema_propuesto": forms.Textarea(attrs={"rows": 3}),
            "justificacion": forms.Textarea(attrs={"rows": 4}),
        }
