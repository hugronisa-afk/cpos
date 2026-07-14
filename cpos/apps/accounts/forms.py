"""Formularios Django para la administración segura de ``accounts``."""

from __future__ import annotations

import re
from typing import Any

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    Cohorte,
    EstadoCohorte,
    EstadoPrograma,
    EstadoUsuario,
    Maestrante,
    Permiso,
    Programa,
    Rol,
    RolPermiso,
    UsuarioCPOS,
)
from .services import (
    SIGLAS_ROL,
    actualizar_usuario_seguro,
    cambiar_password_usuario,
    crear_usuario_seguro,
    generar_nombre_usuario,
    validar_nombre_usuario_disponible,
)


class ContextoAuditoriaMixin:
    """Conserva actor y request sin convertirlos en campos del formulario."""

    def __init__(self, *args, actor=None, request=None, **kwargs):
        self.actor = actor
        self.request = request
        super().__init__(*args, **kwargs)


class EstilosFormularioMixin:
    """Añade atributos accesibles sin depender de JavaScript."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(campo.widget, forms.CheckboxSelectMultiple):
                campo.widget.attrs.setdefault("class", "checkbox-list")
            else:
                campo.widget.attrs.setdefault("class", "form-control")


def _normalizar_cedula_formulario(cedula: Any) -> str:
    cedula_normalizada = re.sub(r"[\s-]+", "", str(cedula or ""))
    if not cedula_normalizada:
        raise ValidationError("La cédula es obligatoria.")
    if not cedula_normalizada.isdigit():
        raise ValidationError("La cédula debe contener solo números.")
    if len(cedula_normalizada) > 20:
        raise ValidationError("La cédula no puede superar 20 dígitos.")
    return cedula_normalizada


def _normalizar_correo_formulario(correo: Any) -> str:
    return str(correo or "").strip().lower()


def _aplicar_fecha_actualizacion(instancia):
    instancia.fecha_actualizacion = timezone.now()
    return instancia


def _actor_es_supervisor(actor) -> bool:
    return bool(
        isinstance(actor, UsuarioCPOS)
        and actor.is_active
        and actor.rol.esta_activo
        and actor.rol.nombre.strip().lower() == "supervisor"
    )


class LoginForm(EstilosFormularioMixin, forms.Form):
    nombre_usuario = forms.CharField(
        label="Nombre de usuario",
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autocapitalize": "characters",
                "placeholder": "1206950436-MST",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Contraseña",
            },
            render_value=False,
        ),
    )

    def clean_nombre_usuario(self):
        return self.cleaned_data["nombre_usuario"].strip().upper()


class UsuarioDatosMixin:
    def clean_nombres(self):
        nombres = self.cleaned_data["nombres"].strip()
        if not nombres:
            raise ValidationError("Los nombres son obligatorios.")
        return nombres

    def clean_apellidos(self):
        apellidos = self.cleaned_data["apellidos"].strip()
        if not apellidos:
            raise ValidationError("Los apellidos son obligatorios.")
        return apellidos

    def clean_cedula(self):
        return _normalizar_cedula_formulario(self.cleaned_data["cedula"])

    def clean_correo(self):
        return _normalizar_correo_formulario(self.cleaned_data["correo"])

    def clean_telefono(self):
        telefono = str(self.cleaned_data.get("telefono") or "").strip()
        return telefono or None

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        if not rol.esta_activo:
            raise ValidationError("No se puede asignar un rol inactivo.")
        actor = getattr(self, "actor", None)
        if isinstance(actor, UsuarioCPOS) and not _actor_es_supervisor(actor):
            instancia = getattr(self, "instance", None)
            editando_cuenta_propia = bool(
                instancia
                and instancia.pk
                and instancia.pk == actor.pk
            )
            if editando_cuenta_propia:
                if rol.pk != actor.rol_id:
                    raise ValidationError("No puede modificar su propio rol.")
            elif rol.nombre.strip().lower() != "maestrante":
                raise ValidationError(
                    "Solo un supervisor puede asignar este rol."
                )
        return rol

    def _validar_identificadores(self, cleaned_data, excluir_usuario_id=None):
        cedula = cleaned_data.get("cedula")
        rol = cleaned_data.get("rol")
        correo = cleaned_data.get("correo")
        consulta = UsuarioCPOS.objects.all()
        if excluir_usuario_id is not None:
            consulta = consulta.exclude(pk=excluir_usuario_id)

        if correo and consulta.filter(correo__iexact=correo).exists():
            self.add_error("correo", "Ya existe una cuenta con este correo.")
        if cedula and rol:
            if consulta.filter(cedula=cedula, rol=rol).exists():
                self.add_error(
                    "cedula",
                    "Ya existe una cuenta con esta cédula y este rol.",
                )
            nombre_usuario = generar_nombre_usuario(cedula, rol)
            if not validar_nombre_usuario_disponible(
                nombre_usuario,
                excluir_usuario_id=excluir_usuario_id,
            ):
                self.add_error(
                    "cedula",
                    "El nombre de usuario generado ya está registrado.",
                )


class UsuarioCreateForm(
    ContextoAuditoriaMixin,
    EstilosFormularioMixin,
    UsuarioDatosMixin,
    forms.ModelForm,
):
    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"},
            render_value=False,
        ),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"},
            render_value=False,
        ),
    )

    class Meta:
        model = UsuarioCPOS
        fields = (
            "nombres",
            "apellidos",
            "cedula",
            "correo",
            "telefono",
            "rol",
            "estado",
        )
        labels = {
            "cedula": "Cédula",
            "correo": "Correo institucional",
            "telefono": "Teléfono",
            "rol": "Rol",
            "estado": "Estado inicial",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        roles = Rol.objects.filter(esta_activo=True)
        if isinstance(self.actor, UsuarioCPOS) and not _actor_es_supervisor(self.actor):
            roles = roles.filter(nombre__iexact="maestrante")
        self.fields["rol"].queryset = roles.order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()
        self._validar_identificadores(cleaned_data)

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif password1:
            usuario_temporal = UsuarioCPOS(
                nombres=cleaned_data.get("nombres", ""),
                apellidos=cleaned_data.get("apellidos", ""),
                cedula=cleaned_data.get("cedula", ""),
                correo=cleaned_data.get("correo", ""),
                nombre_usuario=(
                    generar_nombre_usuario(cleaned_data["cedula"], cleaned_data["rol"])
                    if cleaned_data.get("cedula") and cleaned_data.get("rol")
                    else ""
                ),
            )
            try:
                password_validation.validate_password(password1, user=usuario_temporal)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    def save(self, commit=True):
        if not commit:
            raise ValueError(
                "UsuarioCreateForm requiere commit=True para usar el servicio seguro."
            )
        return crear_usuario_seguro(
            rol=self.cleaned_data["rol"],
            nombres=self.cleaned_data["nombres"],
            apellidos=self.cleaned_data["apellidos"],
            cedula=self.cleaned_data["cedula"],
            correo=self.cleaned_data["correo"],
            telefono=self.cleaned_data.get("telefono"),
            estado=self.cleaned_data["estado"],
            contrasena=self.cleaned_data["password1"],
            actor=self.actor,
            request=self.request,
        )


class UsuarioUpdateForm(
    ContextoAuditoriaMixin,
    EstilosFormularioMixin,
    UsuarioDatosMixin,
    forms.ModelForm,
):
    class Meta:
        model = UsuarioCPOS
        fields = (
            "nombres",
            "apellidos",
            "cedula",
            "correo",
            "telefono",
            "rol",
            "estado",
        )
        labels = UsuarioCreateForm.Meta.labels

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        roles = Rol.objects.filter(esta_activo=True)
        if self.instance and self.instance.rol_id:
            roles = Rol.objects.filter(Q(esta_activo=True) | Q(pk=self.instance.rol_id))
        if isinstance(self.actor, UsuarioCPOS) and not _actor_es_supervisor(self.actor):
            if self.instance and self.instance.pk == self.actor.pk:
                roles = roles.filter(pk=self.actor.rol_id)
            else:
                roles = roles.filter(nombre__iexact="maestrante")
        self.fields["rol"].queryset = roles.distinct().order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()
        self._validar_identificadores(
            cleaned_data,
            excluir_usuario_id=self.instance.pk,
        )
        if (
            isinstance(self.actor, UsuarioCPOS)
            and self.instance.pk == self.actor.pk
            and cleaned_data.get("estado") != EstadoUsuario.ACTIVO
        ):
            self.add_error("estado", "No puede desactivar su propia cuenta.")
        return cleaned_data

    def save(self, commit=True):
        if not commit:
            raise ValueError(
                "UsuarioUpdateForm requiere commit=True para usar el servicio seguro."
            )
        return actualizar_usuario_seguro(
            self.instance,
            rol=self.cleaned_data["rol"],
            nombres=self.cleaned_data["nombres"],
            apellidos=self.cleaned_data["apellidos"],
            cedula=self.cleaned_data["cedula"],
            correo=self.cleaned_data["correo"],
            telefono=self.cleaned_data.get("telefono"),
            estado=self.cleaned_data["estado"],
            actor=self.actor,
            request=self.request,
        )


class UsuarioEstadoForm(ContextoAuditoriaMixin, EstilosFormularioMixin, forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado", choices=EstadoUsuario.choices)

    def __init__(self, *args, usuario, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        self.fields["estado"].initial = usuario.estado

    def clean_estado(self):
        estado = self.cleaned_data["estado"]
        if (
            isinstance(self.actor, UsuarioCPOS)
            and self.actor.pk == self.usuario.pk
            and estado != EstadoUsuario.ACTIVO
        ):
            raise ValidationError("No puede inactivar o bloquear su propia cuenta.")
        return estado

    def save(self):
        return actualizar_usuario_seguro(
            self.usuario,
            estado=self.cleaned_data["estado"],
            actor=self.actor,
            request=self.request,
        )


class UsuarioPasswordForm(ContextoAuditoriaMixin, EstilosFormularioMixin, forms.Form):
    nueva_password = forms.CharField(
        label="Nueva contraseña",
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"},
            render_value=False,
        ),
    )
    confirmacion_password = forms.CharField(
        label="Confirmar contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password"},
            render_value=False,
        ),
    )

    def __init__(
        self,
        *args,
        usuario,
        conservar_session_key=None,
        **kwargs,
    ):
        self.usuario = usuario
        self.conservar_session_key = conservar_session_key
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        nueva = cleaned_data.get("nueva_password")
        confirmacion = cleaned_data.get("confirmacion_password")
        if nueva and confirmacion and nueva != confirmacion:
            self.add_error("confirmacion_password", "Las contraseñas no coinciden.")
        elif nueva:
            try:
                password_validation.validate_password(nueva, user=self.usuario)
            except ValidationError as error:
                self.add_error("nueva_password", error)
        return cleaned_data

    def save(self):
        return cambiar_password_usuario(
            self.usuario,
            self.cleaned_data["nueva_password"],
            self.cleaned_data["confirmacion_password"],
            actor=self.actor,
            request=self.request,
            conservar_session_key=self.conservar_session_key,
        )


class RolForm(EstilosFormularioMixin, forms.ModelForm):
    class Meta:
        model = Rol
        fields = ("nombre", "descripcion", "nivel_autoridad", "esta_activo")
        labels = {
            "nombre": "Nombre",
            "descripcion": "Descripción",
            "nivel_autoridad": "Nivel de autoridad",
            "esta_activo": "Rol activo",
        }
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip().lower()
        if nombre not in SIGLAS_ROL:
            raise ValidationError(
                "El rol debe ser maestrante, tutor, coordinador o supervisor."
            )
        consulta = Rol.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            consulta = consulta.exclude(pk=self.instance.pk)
        if consulta.exists():
            raise ValidationError("Ya existe un rol con este nombre.")
        return nombre

    def save(self, commit=True):
        instancia = _aplicar_fecha_actualizacion(super().save(commit=False))
        if commit:
            instancia.save()
        return instancia


class PermisoForm(EstilosFormularioMixin, forms.ModelForm):
    class Meta:
        model = Permiso
        fields = (
            "codigo",
            "nombre",
            "modulo",
            "descripcion",
            "esta_activo",
        )
        labels = {
            "codigo": "Código",
            "nombre": "Nombre",
            "modulo": "Módulo",
            "descripcion": "Descripción",
            "esta_activo": "Permiso activo",
        }
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", codigo):
            raise ValidationError(
                "Use únicamente letras mayúsculas, números y guiones bajos."
            )
        consulta = Permiso.objects.filter(codigo__iexact=codigo)
        if self.instance.pk:
            consulta = consulta.exclude(pk=self.instance.pk)
        if consulta.exists():
            raise ValidationError("Ya existe un permiso con este código.")
        return codigo

    def clean_modulo(self):
        return self.cleaned_data["modulo"].strip().lower()

    def save(self, commit=True):
        instancia = _aplicar_fecha_actualizacion(super().save(commit=False))
        if commit:
            instancia.save()
        return instancia


class RolPermisoForm(EstilosFormularioMixin, forms.Form):
    rol = forms.ModelChoiceField(
        label="Rol",
        queryset=Rol.objects.filter(esta_activo=True).order_by("nombre"),
    )
    permisos = forms.ModelMultipleChoiceField(
        label="Permisos asignados",
        queryset=Permiso.objects.filter(esta_activo=True).order_by("modulo", "codigo"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, rol=None, **kwargs):
        self.rol_objeto = rol
        super().__init__(*args, **kwargs)
        if rol is not None:
            self.fields["rol"].initial = rol
            self.fields["rol"].disabled = True
            self.fields["permisos"].initial = Permiso.objects.filter(
                asignaciones_roles__rol=rol
            )

    def save(self):
        rol = self.cleaned_data["rol"]
        permisos = self.cleaned_data["permisos"]
        ids_deseados = set(permisos.values_list("pk", flat=True))

        with transaction.atomic():
            asignaciones = RolPermiso.objects.select_for_update().filter(rol=rol)
            ids_actuales = set(asignaciones.values_list("permiso_id", flat=True))
            asignaciones.filter(permiso_id__in=ids_actuales - ids_deseados).delete()
            RolPermiso.objects.bulk_create(
                [
                    RolPermiso(rol=rol, permiso_id=permiso_id)
                    for permiso_id in ids_deseados - ids_actuales
                ]
            )
        return rol


class ProgramaForm(EstilosFormularioMixin, forms.ModelForm):
    class Meta:
        model = Programa
        fields = ("nombre", "codigo", "descripcion", "coordinador", "estado")
        labels = {
            "nombre": "Nombre del programa",
            "codigo": "Código",
            "descripcion": "Descripción",
            "coordinador": "Coordinador responsable",
            "estado": "Estado",
        }
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coordinadores = UsuarioCPOS.objects.filter(
            estado=EstadoUsuario.ACTIVO,
            rol__nombre__iexact="coordinador",
            rol__esta_activo=True,
        )
        if self.instance and self.instance.coordinador_id:
            coordinadores = UsuarioCPOS.objects.filter(
                Q(pk=self.instance.coordinador_id)
                | Q(
                    estado=EstadoUsuario.ACTIVO,
                    rol__nombre__iexact="coordinador",
                    rol__esta_activo=True,
                )
            )
        self.fields["coordinador"].queryset = coordinadores.distinct().order_by(
            "apellidos", "nombres"
        )

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()

    def clean_coordinador(self):
        coordinador = self.cleaned_data.get("coordinador")
        if coordinador and (
            not coordinador.is_active
            or not coordinador.rol.esta_activo
            or coordinador.rol.nombre.lower() != "coordinador"
        ):
            raise ValidationError("Seleccione un coordinador activo.")
        return coordinador

    def save(self, commit=True):
        instancia = _aplicar_fecha_actualizacion(super().save(commit=False))
        if commit:
            instancia.save()
        return instancia


class CohorteForm(EstilosFormularioMixin, forms.ModelForm):
    class Meta:
        model = Cohorte
        fields = (
            "programa",
            "nombre",
            "fecha_inicio",
            "fecha_fin",
            "estado",
        )
        labels = {
            "programa": "Programa",
            "nombre": "Nombre de la cohorte",
            "fecha_inicio": "Fecha de inicio",
            "fecha_fin": "Fecha de finalización",
            "estado": "Estado",
        }
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        programas = Programa.objects.filter(estado=EstadoPrograma.ACTIVO)
        if self.instance and self.instance.programa_id:
            programas = Programa.objects.filter(
                Q(estado=EstadoPrograma.ACTIVO) | Q(pk=self.instance.programa_id)
            )
        self.fields["programa"].queryset = programas.distinct().order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error(
                "fecha_fin",
                "La fecha de finalización no puede ser anterior al inicio.",
            )
        return cleaned_data

    def save(self, commit=True):
        instancia = _aplicar_fecha_actualizacion(super().save(commit=False))
        if commit:
            instancia.save()
        return instancia


class MaestranteForm(EstilosFormularioMixin, forms.ModelForm):
    class Meta:
        model = Maestrante
        fields = (
            "usuario",
            "programa",
            "cohorte",
            "codigo_matricula",
            "estado_titulacion",
        )
        labels = {
            "usuario": "Cuenta de maestrante",
            "programa": "Programa",
            "cohorte": "Cohorte",
            "codigo_matricula": "Código de matrícula",
            "estado_titulacion": "Estado de titulación",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuarios = UsuarioCPOS.objects.filter(
            estado=EstadoUsuario.ACTIVO,
            rol__nombre__iexact="maestrante",
            rol__esta_activo=True,
            perfil_maestrante__isnull=True,
        )
        if self.instance and self.instance.usuario_id:
            usuarios = UsuarioCPOS.objects.filter(
                Q(pk=self.instance.usuario_id)
                | Q(
                    estado=EstadoUsuario.ACTIVO,
                    rol__nombre__iexact="maestrante",
                    rol__esta_activo=True,
                    perfil_maestrante__isnull=True,
                )
            )
        self.fields["usuario"].queryset = usuarios.distinct().order_by(
            "apellidos", "nombres"
        )

        programas = Programa.objects.filter(estado=EstadoPrograma.ACTIVO)
        if self.instance and self.instance.programa_id:
            programas = Programa.objects.filter(
                Q(estado=EstadoPrograma.ACTIVO) | Q(pk=self.instance.programa_id)
            )
        self.fields["programa"].queryset = programas.distinct().order_by("nombre")

        cohortes = Cohorte.objects.filter(estado=EstadoCohorte.ACTIVA)
        if self.instance and self.instance.cohorte_id:
            cohortes = Cohorte.objects.filter(
                Q(estado=EstadoCohorte.ACTIVA) | Q(pk=self.instance.cohorte_id)
            )
        self.fields["cohorte"].queryset = cohortes.distinct().order_by(
            "programa__nombre", "-fecha_inicio"
        )

    def clean_codigo_matricula(self):
        return self.cleaned_data["codigo_matricula"].strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        usuario = cleaned_data.get("usuario")
        programa = cleaned_data.get("programa")
        cohorte = cleaned_data.get("cohorte")

        if usuario and (
            not usuario.is_active
            or not usuario.rol.esta_activo
            or usuario.rol.nombre.lower() != "maestrante"
        ):
            self.add_error("usuario", "Seleccione una cuenta de maestrante activa.")
        if programa and cohorte and cohorte.programa_id != programa.pk:
            self.add_error(
                "cohorte",
                "La cohorte seleccionada no pertenece al programa indicado.",
            )
        return cleaned_data

    def save(self, commit=True):
        instancia = _aplicar_fecha_actualizacion(super().save(commit=False))
        if commit:
            instancia.save()
        return instancia


class PerfilForm(
    ContextoAuditoriaMixin,
    EstilosFormularioMixin,
    forms.ModelForm,
):
    class Meta:
        model = UsuarioCPOS
        fields = ("nombres", "apellidos", "correo", "telefono")
        labels = {
            "nombres": "Nombres",
            "apellidos": "Apellidos",
            "correo": "Correo institucional",
            "telefono": "Teléfono",
        }

    def clean_nombres(self):
        nombres = self.cleaned_data["nombres"].strip()
        if not nombres:
            raise ValidationError("Los nombres son obligatorios.")
        return nombres

    def clean_apellidos(self):
        apellidos = self.cleaned_data["apellidos"].strip()
        if not apellidos:
            raise ValidationError("Los apellidos son obligatorios.")
        return apellidos

    def clean_correo(self):
        correo = _normalizar_correo_formulario(self.cleaned_data["correo"])
        if (
            UsuarioCPOS.objects.filter(correo__iexact=correo)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def clean_telefono(self):
        telefono = str(self.cleaned_data.get("telefono") or "").strip()
        return telefono or None

    def save(self, commit=True):
        if not commit:
            raise ValueError("PerfilForm requiere commit=True para usar el servicio seguro.")
        return actualizar_usuario_seguro(
            self.instance,
            nombres=self.cleaned_data["nombres"],
            apellidos=self.cleaned_data["apellidos"],
            correo=self.cleaned_data["correo"],
            telefono=self.cleaned_data.get("telefono"),
            actor=self.actor,
            request=self.request,
        )
