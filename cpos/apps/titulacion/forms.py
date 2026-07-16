from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import EstadoUsuario, Programa, UsuarioCPOS

from .modalidades import CATALOGO_TIPOS_EVIDENCIA, modalidades_disponibles

from .models import (
    ArchivoProyecto,
    Articulo,
    AsignacionTutor,
    AsistenciaTutoria,
    AutorizacionNovenaTutoria,
    ConfiguracionModalidadPrograma,
    DisponibilidadTutor,
    EntregaEtapa,
    EscalaCalificacion,
    EstadoSolicitudCambioTutor,
    EstadoProyecto,
    EtapaProducto,
    ExamenComplexivo,
    Grabacion,
    ModalidadConfigurada,
    ModalidadProyecto,
    OnboardingMaestrante,
    ProyectoTitulacion,
    ReprogramacionTutoria,
    SolicitudCambioTutor,
    SolicitudCambioTema,
    SolicitudCambioModalidad,
    TipoArchivo,
    TipoGrabacion,
    Tutor,
    TutorPrograma,
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
    programas = forms.ModelMultipleChoiceField(
        queryset=Programa.objects.none(),
        label="Programas habilitados",
        help_text="El tutor solo podrá asignarse a proyectos de estos programas.",
    )
    usuario = UsuarioTutorChoiceField(
        queryset=UsuarioCPOS.objects.none(),
        label="Usuario tutor",
        help_text="Solo se muestran cuentas activas con rol tutor y sin perfil asociado.",
    )

    class Meta:
        model = Tutor
        fields = (
            "usuario",
            "programas",
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

    def __init__(self, *args, usuario_actual=None, **kwargs):
        self.usuario_actual = usuario_actual
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

        programas = Programa.objects.filter(estado="activo")
        rol = str(
            getattr(getattr(usuario_actual, "rol", None), "nombre", "")
        ).strip().lower()
        if rol == "coordinador":
            programas = programas.filter(coordinador=usuario_actual)
        self.fields["programas"].queryset = programas.order_by("nombre")
        if self.instance and self.instance.pk:
            self.initial["programas"] = list(
                self.instance.vinculos_programa.filter(esta_activo=True).values_list(
                    "programa_id", flat=True
                )
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

    def save(self, commit=True):
        tutor = super().save(commit=commit)
        if commit:
            seleccionados = set(
                self.cleaned_data["programas"].values_list("pk", flat=True)
            )
            TutorPrograma.objects.filter(tutor=tutor).exclude(
                programa_id__in=seleccionados
            ).update(esta_activo=False)
            for programa_id in seleccionados:
                TutorPrograma.objects.update_or_create(
                    tutor=tutor,
                    programa_id=programa_id,
                    defaults={"esta_activo": True},
                )
        return tutor


class ProyectoForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = ProyectoTitulacion
        fields = ("tema", "modalidad")
        labels = {"tema": "Tema de titulación", "modalidad": "Modalidad"}
        widgets = {"tema": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, programa=None, **kwargs):
        self.programa = programa
        super().__init__(*args, **kwargs)
        actual = self.instance.modalidad if self.instance and self.instance.pk else None
        self.fields["modalidad"].choices = modalidades_disponibles(
            programa,
            incluir_modalidad=actual,
        )
        self.fields["modalidad"].help_text = (
            "La modalidad define las evidencias y el producto final. "
            "Después de la aprobación solo podrá cambiarse mediante solicitud formal."
        )

    def clean_tema(self):
        tema = self.cleaned_data["tema"].strip()
        if not tema:
            raise ValidationError("El tema es obligatorio.")
        return tema

    def clean_modalidad(self):
        modalidad = self.cleaned_data["modalidad"]
        permitidas = {codigo for codigo, _ in self.fields["modalidad"].choices}
        if modalidad not in permitidas:
            raise ValidationError(
                "Esta modalidad no está habilitada para el programa del maestrante."
            )
        return modalidad


class ConfiguracionModalidadProgramaForm(
    FormularioEstilizadoMixin,
    forms.ModelForm,
):
    tipos_evidencia = forms.MultipleChoiceField(
        label="Tipos de evidencia permitidos",
        choices=CATALOGO_TIPOS_EVIDENCIA,
        widget=forms.CheckboxSelectMultiple,
        help_text="Estos tipos aparecerán al cargar evidencias para esta modalidad.",
    )

    class Meta:
        model = ConfiguracionModalidadPrograma
        fields = (
            "programa",
            "nombre",
            "descripcion",
            "tipos_evidencia",
            "producto_final_nombre",
            "tipo_archivo_final",
            "esta_activa",
        )
        labels = {
            "nombre": "Nombre de la modalidad",
            "descripcion": "Descripción y alcance",
            "producto_final_nombre": "Producto final requerido",
            "tipo_archivo_final": "Tipo de archivo final",
            "esta_activa": "Disponible para nuevos proyectos",
        }
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        programas = Programa.objects.filter(estado="activo")
        rol = str(getattr(getattr(usuario, "rol", None), "nombre", "")).lower()
        if rol == "coordinador":
            programas = programas.filter(coordinador=usuario)
        self.fields["programa"].queryset = programas.order_by("nombre")
        if self.instance and self.instance.pk:
            self.initial["tipos_evidencia"] = self.instance.tipos_evidencia

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if not nombre:
            raise ValidationError("El nombre es obligatorio.")
        return nombre

    def clean_descripcion(self):
        descripcion = self.cleaned_data["descripcion"].strip()
        if not descripcion:
            raise ValidationError("La descripción es obligatoria.")
        return descripcion

    def clean_producto_final_nombre(self):
        nombre = self.cleaned_data["producto_final_nombre"].strip()
        if not nombre:
            raise ValidationError("Defina el producto final de esta modalidad.")
        return nombre

    def save(self, commit=True):
        instancia = super().save(commit=False)
        instancia.tipos_evidencia = list(self.cleaned_data["tipos_evidencia"])
        if commit:
            instancia.save()
        return instancia


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


class RevisionPasoAprobacionForm(FormularioEstilizadoMixin, forms.Form):
    decision = forms.ChoiceField(label="Decisión")
    observaciones = forms.CharField(
        required=False,
        label="Observaciones",
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    def __init__(self, *args, permite_observar=False, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = [("aprobar", "Aprobar y continuar")]
        if permite_observar:
            opciones.append(("observar", "Observar y devolver para corrección"))
        opciones.append(("rechazar", "Rechazar definitivamente"))
        self.fields["decision"].choices = opciones

    def clean(self):
        datos = super().clean()
        if (
            datos.get("decision") in {"observar", "rechazar"}
            and not str(datos.get("observaciones") or "").strip()
        ):
            self.add_error(
                "observaciones",
                "Debe explicar la observación o el motivo del rechazo.",
            )
        return datos

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["numero_resolucion"].required = True
        self.fields["fecha_aprobacion"].required = True
        if not (self.instance and self.instance.documento_resolucion_url):
            self.fields["documento_resolucion"].required = True

    def clean_documento_resolucion(self):
        archivo = self.cleaned_data.get("documento_resolucion")
        if archivo:
            validar_archivo_subido(archivo, {"pdf"}, MAX_DOCUMENTO)
        return archivo


class TutorAsignacionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, tutor):
        carga = getattr(tutor, "carga_activa", 0)
        return (
            f"{tutor.usuario.nombre_completo} · "
            f"{tutor.especialidad or 'Sin especialidad'} · {carga} asignaciones activas"
        )


def _tutores_para_proyecto(proyecto, excluir_tutor_id=None):
    consulta = Tutor.objects.select_related("usuario").filter(
        estado="disponible",
        usuario__estado="activo",
        usuario__rol__esta_activo=True,
        vinculos_programa__programa_id=proyecto.maestrante.programa_id,
        vinculos_programa__esta_activo=True,
        disponibilidades__esta_activa=True,
    )
    if excluir_tutor_id:
        consulta = consulta.exclude(pk=excluir_tutor_id)
    return consulta.annotate(
        carga_activa=Count(
            "asignaciones",
            filter=Q(asignaciones__estado="activo"),
            distinct=True,
        )
    ).distinct().order_by("usuario__apellidos", "usuario__nombres")


class AsignacionTutorForm(FormularioEstilizadoMixin, forms.ModelForm):
    tutor = TutorAsignacionChoiceField(queryset=Tutor.objects.none())

    class Meta:
        model = AsignacionTutor
        fields = ("tutor",)

    def __init__(self, *args, proyecto=None, **kwargs):
        self.proyecto = proyecto
        super().__init__(*args, **kwargs)
        if proyecto is not None:
            self.fields["tutor"].queryset = _tutores_para_proyecto(proyecto)


class SolicitudCambioTutorForm(FormularioEstilizadoMixin, forms.ModelForm):
    tutor_propuesto = TutorAsignacionChoiceField(
        queryset=Tutor.objects.none(),
        label="Tutor propuesto",
    )

    class Meta:
        model = SolicitudCambioTutor
        fields = ("tutor_propuesto", "motivo")
        widgets = {"motivo": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, proyecto=None, asignacion_actual=None, **kwargs):
        self.proyecto = proyecto
        self.asignacion_actual = asignacion_actual
        super().__init__(*args, **kwargs)
        if proyecto is not None:
            self.fields["tutor_propuesto"].queryset = _tutores_para_proyecto(
                proyecto,
                excluir_tutor_id=getattr(asignacion_actual, "tutor_id", None),
            )

    def clean_motivo(self):
        motivo = str(self.cleaned_data.get("motivo") or "").strip()
        if not motivo:
            raise ValidationError("Explique por qué solicita el cambio de tutor.")
        return motivo


class ResolucionCambioTutorForm(FormularioEstilizadoMixin, forms.Form):
    decision = forms.ChoiceField(
        choices=(("aprobar", "Aprobar cambio"), ("rechazar", "Rechazar cambio"))
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def clean(self):
        datos = super().clean()
        if (
            datos.get("decision") == "rechazar"
            and not str(datos.get("observaciones") or "").strip()
        ):
            self.add_error("observaciones", "Explique el motivo del rechazo.")
        return datos


class DisponibilidadTutorForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = DisponibilidadTutor
        fields = ("dia_semana", "hora_inicio", "hora_fin")
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        datos = super().clean()
        inicio = datos.get("hora_inicio")
        fin = datos.get("hora_fin")
        if inicio and fin and fin <= inicio:
            self.add_error("hora_fin", "Debe ser posterior a la hora de inicio.")
        return datos


class TutoriaForm(FormularioEstilizadoMixin, forms.ModelForm):
    numero_tutoria = forms.TypedChoiceField(coerce=int, label="Número de tutoría")

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
        labels = {"enlace_virtual": "Enlace HTTPS de la sala virtual"}

    def __init__(self, *args, proyecto=None, **kwargs):
        self.proyecto = proyecto
        super().__init__(*args, **kwargs)
        ocupados = set()
        limite = 8
        if proyecto is not None:
            ocupados = set(
                proyecto.tutorias.values_list("numero_tutoria", flat=True)
            )
            if getattr(proyecto, "pk", None):
                if AutorizacionNovenaTutoria.objects.filter(proyecto_id=proyecto.pk).exists():
                    limite = 9
        self.fields["numero_tutoria"].choices = [
            (numero, f"Tutoría {numero}" + (" (excepcional autorizada)" if numero == 9 else ""))
            for numero in range(1, limite + 1)
            if numero not in ocupados
        ]
        self.fields["enlace_virtual"].required = True

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha < timezone.localdate():
            raise ValidationError("La tutoría debe programarse en una fecha futura.")
        return fecha

    def clean_enlace_virtual(self):
        enlace = str(self.cleaned_data.get("enlace_virtual") or "").strip()
        if not enlace.lower().startswith("https://"):
            raise ValidationError("Use un enlace HTTPS para la sala virtual.")
        return enlace


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


    def __init__(self, *args, tutoria=None, **kwargs):
        self.tutoria = tutoria
        super().__init__(*args, **kwargs)

    def clean_fecha_nueva(self):
        fecha = self.cleaned_data["fecha_nueva"]
        if fecha < timezone.localdate():
            raise ValidationError("La nueva fecha no puede estar en el pasado.")
        return fecha

    def clean_motivo(self):
        motivo = str(self.cleaned_data.get("motivo") or "").strip()
        if not motivo:
            raise ValidationError("Explique el motivo de la reprogramación.")
        return motivo

    def clean(self):
        datos = super().clean()
        inicio = datos.get("hora_inicio_nueva")
        fin = datos.get("hora_fin_nueva")
        if inicio and fin and fin <= inicio:
            self.add_error("hora_fin_nueva", "Debe ser posterior a la hora de inicio.")
        if self.tutoria and all(
            datos.get(campo)
            for campo in ("fecha_nueva", "hora_inicio_nueva", "hora_fin_nueva")
        ):
            sin_cambio = (
                datos["fecha_nueva"] == self.tutoria.fecha
                and datos["hora_inicio_nueva"] == self.tutoria.hora_inicio
                and datos["hora_fin_nueva"] == self.tutoria.hora_fin
            )
            if sin_cambio:
                self.add_error(None, "Seleccione una fecha u horario diferente.")
        return datos


class ArchivoProyectoForm(FormularioEstilizadoMixin, forms.Form):
    tipo_archivo = forms.ChoiceField(
        choices=(
            (TipoArchivo.WORD, TipoArchivo.WORD.label),
            (TipoArchivo.PDF, TipoArchivo.PDF.label),
            (TipoArchivo.ANEXO, TipoArchivo.ANEXO.label),
        )
    )
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


class SolicitudCambioModalidadForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = SolicitudCambioModalidad
        fields = ("modalidad_propuesta", "justificacion")
        labels = {
            "modalidad_propuesta": "Nueva modalidad",
            "justificacion": "Justificación académica",
        }
        widgets = {"justificacion": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, proyecto=None, **kwargs):
        self.proyecto = proyecto
        super().__init__(*args, **kwargs)
        programa = proyecto.maestrante.programa if proyecto else None
        actual = proyecto.modalidad if proyecto else None
        self.fields["modalidad_propuesta"].choices = tuple(
            (codigo, nombre)
            for codigo, nombre in modalidades_disponibles(programa)
            if codigo != actual
        )

    def clean_modalidad_propuesta(self):
        modalidad = self.cleaned_data["modalidad_propuesta"]
        permitidas = {
            codigo for codigo, _ in self.fields["modalidad_propuesta"].choices
        }
        if modalidad not in permitidas:
            raise ValidationError("La modalidad propuesta no está disponible.")
        return modalidad

    def clean_justificacion(self):
        justificacion = self.cleaned_data["justificacion"].strip()
        if not justificacion:
            raise ValidationError("La justificación es obligatoria.")
        return justificacion


# ---------------------------------------------------------------------------
# Fase 7A — Onboarding
# ---------------------------------------------------------------------------


class SeleccionModalidadOnboardingForm(FormularioEstilizadoMixin, forms.Form):
    modalidad = forms.ChoiceField(label="Modalidad de titulación", choices=())

    def __init__(self, *args, opciones=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modalidad"].choices = opciones

    def clean_modalidad(self):
        modalidad = self.cleaned_data["modalidad"]
        permitidas = {codigo for codigo, _ in self.fields["modalidad"].choices}
        if modalidad not in permitidas:
            raise ValidationError("Seleccione una modalidad activa para su programa.")
        return modalidad


# ---------------------------------------------------------------------------
# Fase 7B — Modalidades configurables y sus etapas
# ---------------------------------------------------------------------------


class ModalidadConfiguradaForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = ModalidadConfigurada
        fields = (
            "programa",
            "tipo_modalidad",
            "nombre",
            "descripcion",
            "requiere_tutor",
            "esta_activa",
        )
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}
        labels = {
            "programa": "Programa (vacío = global)",
            "esta_activa": "Disponible para nuevos onboardings",
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programa"].required = False
        rol = str(getattr(getattr(usuario, "rol", None), "nombre", "")).lower()
        if rol == "coordinador":
            self.fields["programa"].queryset = Programa.objects.filter(coordinador=usuario)


class EtapaProductoForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = EtapaProducto
        fields = ("modalidad", "orden", "codigo", "nombre", "descripcion", "es_obligatoria", "esta_activa")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}


# ---------------------------------------------------------------------------
# Fase 7C — Novena tutoría excepcional
# ---------------------------------------------------------------------------


class AutorizacionNovenaTutoriaForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = AutorizacionNovenaTutoria
        fields = ("motivo",)
        widgets = {"motivo": forms.Textarea(attrs={"rows": 4})}

    def clean_motivo(self):
        motivo = self.cleaned_data["motivo"].strip()
        if not motivo:
            raise ValidationError("Explique el motivo de la novena tutoría.")
        return motivo


# ---------------------------------------------------------------------------
# Fase 7D — Entregas por etapa, examen complexivo y escala de calificación
# ---------------------------------------------------------------------------


class EntregaEtapaForm(FormularioEstilizadoMixin, forms.Form):
    archivo = forms.FileField(label="Archivo de la entrega", required=False)
    comentario = forms.CharField(
        label="Comentario",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class EvaluarEntregaEtapaForm(FormularioEstilizadoMixin, forms.Form):
    ESTADOS = (
        ("aprobada", "Aprobar"),
        ("observada", "Observar"),
        ("rechazada", "Rechazar"),
    )
    estado = forms.ChoiceField(label="Resolución", choices=ESTADOS)
    evaluacion = forms.CharField(
        label="Evaluación", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    observaciones = forms.CharField(
        label="Observaciones", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("estado") != "aprobada" and not str(cleaned.get("observaciones") or "").strip():
            raise ValidationError({"observaciones": "Debe registrar observaciones al observar o rechazar."})
        return cleaned


class ExamenComplexivoForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = ExamenComplexivo
        fields = (
            "escala",
            "convocatoria",
            "fecha_hora",
            "tribunal",
            "numero_intento",
            "calificacion",
            "resultado",
            "observaciones",
            "acta_url",
            "fue_reprogramado",
        )
        widgets = {
            "fecha_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "tribunal": forms.Textarea(attrs={"rows": 3}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }


class EscalaCalificacionForm(FormularioEstilizadoMixin, forms.ModelForm):
    class Meta:
        model = EscalaCalificacion
        fields = (
            "programa",
            "modalidad",
            "nombre",
            "nota_minima",
            "nota_maxima",
            "nota_aprobacion",
            "esta_activa",
        )

    def clean(self):
        cleaned = super().clean()
        minima = cleaned.get("nota_minima")
        maxima = cleaned.get("nota_maxima")
        aprobacion = cleaned.get("nota_aprobacion")
        if minima is not None and maxima is not None and maxima <= minima:
            raise ValidationError({"nota_maxima": "Debe ser mayor a la nota mínima."})
        if (
            aprobacion is not None
            and minima is not None
            and maxima is not None
            and not (minima <= aprobacion <= maxima)
        ):
            raise ValidationError({"nota_aprobacion": "Debe estar dentro del rango mínimo-máximo."})
        return cleaned
