"""Vistas de autenticación y administración de la aplicación ``accounts``."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .decorators import permiso_required, rol_required, usuario_activo_required
from .forms import (
    CohorteForm,
    LoginForm,
    MaestranteForm,
    PerfilForm,
    PermisoForm,
    ProgramaForm,
    RolForm,
    RolPermisoForm,
    UsuarioCreateForm,
    UsuarioEstadoForm,
    UsuarioPasswordForm,
    UsuarioUpdateForm,
)
from .models import (
    Bitacora,
    Cohorte,
    EstadoUsuario,
    Maestrante,
    Permiso,
    Programa,
    Rol,
    UsuarioCPOS,
)
from .services import (
    obtener_permisos_usuario,
    redireccion_por_rol,
    registrar_bitacora,
)


MENSAJE_CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos."


def _es_supervisor(usuario):
    return usuario.rol.nombre.strip().lower() == "supervisor"


def _es_coordinador(usuario):
    return usuario.rol.nombre.strip().lower() == "coordinador"


def _paginar(request, consulta, por_pagina=20):
    return Paginator(consulta, por_pagina).get_page(request.GET.get("page"))


def _agregar_error_formulario(formulario, error):
    if hasattr(error, "error_dict"):
        for campo, errores in error.error_dict.items():
            campo_destino = campo if campo in formulario.fields else None
            for error_individual in errores:
                formulario.add_error(campo_destino, error_individual)
    else:
        for error_individual in error.error_list:
            formulario.add_error(None, error_individual)


def _registrar_accion(
    request,
    *,
    modulo,
    accion,
    tabla_afectada,
    registro_id,
    descripcion,
):
    return registrar_bitacora(
        usuario=request.user,
        modulo=modulo,
        accion=accion,
        tabla_afectada=tabla_afectada,
        registro_id=registro_id,
        descripcion=descripcion,
        request=request,
    )


def _programas_visibles_para(usuario):
    consulta = Programa.objects.select_related("coordinador", "coordinador__rol")
    if _es_supervisor(usuario):
        return consulta
    if _es_coordinador(usuario):
        return consulta.filter(coordinador=usuario)
    if usuario.rol.nombre.strip().lower() == "maestrante":
        return consulta.filter(maestrantes__usuario=usuario).distinct()
    return consulta.none()


def _cohortes_visibles_para(usuario):
    return Cohorte.objects.select_related("programa").filter(
        programa__in=_programas_visibles_para(usuario)
    )


def _maestrantes_visibles_para(usuario):
    consulta = Maestrante.objects.select_related(
        "usuario",
        "usuario__rol",
        "programa",
        "cohorte",
    )
    if _es_supervisor(usuario):
        return consulta
    if _es_coordinador(usuario):
        return consulta.filter(programa__coordinador=usuario)
    if usuario.rol.nombre.strip().lower() == "maestrante":
        return consulta.filter(usuario=usuario)
    return consulta.none()


def _usuarios_visibles_para(usuario):
    consulta = UsuarioCPOS.objects.select_related("rol")
    if _es_supervisor(usuario):
        return consulta
    if _es_coordinador(usuario):
        return consulta.filter(
            Q(pk=usuario.pk)
            | Q(perfil_maestrante__programa__coordinador=usuario)
        ).distinct()
    return consulta.filter(pk=usuario.pk)


def _limitar_programa_formulario(formulario, usuario):
    if _es_coordinador(usuario):
        formulario.fields["coordinador"].queryset = UsuarioCPOS.objects.filter(
            pk=usuario.pk
        )
        formulario.fields["coordinador"].initial = usuario
        formulario.fields["coordinador"].disabled = True


def _limitar_cohorte_formulario(formulario, usuario):
    formulario.fields["programa"].queryset = _programas_visibles_para(usuario).order_by(
        "nombre"
    )


def _limitar_maestrante_formulario(formulario, usuario):
    programas = _programas_visibles_para(usuario)
    formulario.fields["programa"].queryset = programas.order_by("nombre")
    formulario.fields["cohorte"].queryset = Cohorte.objects.filter(
        programa__in=programas
    ).order_by("programa__nombre", "-fecha_inicio")


@require_http_methods(["GET", "POST"])
def login_view(request):
    if getattr(request.user, "is_authenticated", False):
        return redirect(redireccion_por_rol(request.user))

    formulario = LoginForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = authenticate(
            request,
            nombre_usuario=formulario.cleaned_data["nombre_usuario"],
            password=formulario.cleaned_data["password"],
        )
        if usuario is not None:
            auth_login(request, usuario)
            siguiente = request.POST.get("next") or request.GET.get("next")
            if siguiente and url_has_allowed_host_and_scheme(
                siguiente,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(siguiente)
            return redirect(redireccion_por_rol(usuario))
        formulario.add_error(None, MENSAJE_CREDENCIALES_INVALIDAS)

    return render(
        request,
        "accounts/login.html",
        {"form": formulario, "next": request.GET.get("next", "")},
    )


@usuario_activo_required
@require_POST
def logout_view(request):
    auth_logout(request)
    messages.success(request, "La sesión se cerró correctamente.")
    return redirect("accounts:login")


@usuario_activo_required
def dashboard_redirect(request):
    return redirect("accounts:dashboard_accounts")


@usuario_activo_required
def dashboard_accounts(request):
    usuario = request.user
    rol = usuario.rol.nombre.strip().lower()
    indicadores = {}
    perfil_maestrante = None

    if _es_supervisor(usuario):
        indicadores = {
            "usuarios": UsuarioCPOS.objects.count(),
            "usuarios_activos": UsuarioCPOS.objects.filter(
                estado=EstadoUsuario.ACTIVO
            ).count(),
            "usuarios_bloqueados": UsuarioCPOS.objects.filter(
                estado=EstadoUsuario.BLOQUEADO
            ).count(),
            "programas": Programa.objects.count(),
            "cohortes": Cohorte.objects.count(),
            "maestrantes": Maestrante.objects.count(),
        }
    elif _es_coordinador(usuario):
        programas = _programas_visibles_para(usuario)
        indicadores = {
            "programas": programas.count(),
            "cohortes": Cohorte.objects.filter(programa__in=programas).count(),
            "maestrantes": Maestrante.objects.filter(programa__in=programas).count(),
            "usuarios_relacionados": _usuarios_visibles_para(usuario)
            .exclude(pk=usuario.pk)
            .count(),
        }
    elif rol == "maestrante":
        perfil_maestrante = (
            Maestrante.objects.select_related("programa", "cohorte")
            .filter(usuario=usuario)
            .first()
        )
        indicadores["perfil_maestrante"] = perfil_maestrante is not None

    return render(
        request,
        "accounts/dashboard.html",
        {
            "page_title": "Panel principal",
            "page_subtitle": f"Vista de {usuario.rol.nombre}",
            "active_page": "dashboard",
            "rol_actual": rol,
            "indicadores": indicadores,
            "perfil_maestrante": perfil_maestrante,
            "permisos": obtener_permisos_usuario(usuario),
        },
    )


@usuario_activo_required
@require_http_methods(["GET", "POST"])
def perfil_usuario(request):
    formulario = PerfilForm(
        request.POST or None,
        instance=request.user,
        actor=request.user,
        request=request,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            formulario.save()
        except ValidationError as error:
            _agregar_error_formulario(formulario, error)
        else:
            messages.success(request, "El perfil se actualizó correctamente.")
            return redirect("accounts:perfil")

    return render(
        request,
        "accounts/perfil.html",
        {
            "form": formulario,
            "page_title": "Mi perfil",
            "active_page": "perfil",
        },
    )


@permiso_required("USUARIO_VER")
def usuarios_list(request):
    consulta = _usuarios_visibles_para(request.user)
    busqueda = request.GET.get("q", "").strip()
    rol_id = request.GET.get("rol", "").strip()
    estado = request.GET.get("estado", "").strip()
    if busqueda:
        consulta = consulta.filter(
            Q(nombres__icontains=busqueda)
            | Q(apellidos__icontains=busqueda)
            | Q(nombre_usuario__icontains=busqueda)
            | Q(correo__icontains=busqueda)
        )
    if rol_id.isdigit():
        consulta = consulta.filter(rol_id=int(rol_id))
    if estado:
        consulta = consulta.filter(estado=estado)

    return render(
        request,
        "accounts/usuarios_list.html",
        {
            "pagina": _paginar(request, consulta),
            "roles": Rol.objects.filter(esta_activo=True),
            "busqueda": busqueda,
            "rol_seleccionado": rol_id,
            "estado_seleccionado": estado,
            "page_title": "Usuarios",
            "active_page": "usuarios",
        },
    )


@permiso_required("USUARIO_CREAR")
@require_http_methods(["GET", "POST"])
def usuario_create(request):
    formulario = UsuarioCreateForm(
        request.POST or None,
        actor=request.user,
        request=request,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            usuario = formulario.save()
        except ValidationError as error:
            _agregar_error_formulario(formulario, error)
        else:
            messages.success(request, "El usuario se creó correctamente.")
            return redirect("accounts:usuario_detail", pk=usuario.pk)
    return render(
        request,
        "accounts/usuario_form.html",
        {"form": formulario, "modo": "crear", "page_title": "Crear usuario"},
    )


@permiso_required("USUARIO_VER")
def usuario_detail(request, pk):
    usuario = get_object_or_404(_usuarios_visibles_para(request.user), pk=pk)
    return render(
        request,
        "accounts/usuario_detail.html",
        {
            "usuario_cpos": usuario,
            "permisos_efectivos": obtener_permisos_usuario(usuario),
            "page_title": "Detalle de usuario",
        },
    )


@permiso_required("USUARIO_EDITAR")
@require_http_methods(["GET", "POST"])
def usuario_update(request, pk):
    usuario = get_object_or_404(_usuarios_visibles_para(request.user), pk=pk)
    formulario = UsuarioUpdateForm(
        request.POST or None,
        instance=usuario,
        actor=request.user,
        request=request,
    )
    if request.method == "POST" and formulario.is_valid():
        try:
            usuario = formulario.save()
        except ValidationError as error:
            _agregar_error_formulario(formulario, error)
        else:
            messages.success(request, "El usuario se actualizó correctamente.")
            return redirect("accounts:usuario_detail", pk=usuario.pk)
    return render(
        request,
        "accounts/usuario_form.html",
        {
            "form": formulario,
            "usuario_cpos": usuario,
            "modo": "editar",
            "page_title": "Editar usuario",
        },
    )


@permiso_required("USUARIO_DESACTIVAR")
@require_POST
def usuario_toggle_estado(request, pk):
    usuario = get_object_or_404(_usuarios_visibles_para(request.user), pk=pk)
    estado_nuevo = (
        EstadoUsuario.INACTIVO
        if usuario.estado == EstadoUsuario.ACTIVO
        else EstadoUsuario.ACTIVO
    )
    formulario = UsuarioEstadoForm(
        {"estado": estado_nuevo},
        usuario=usuario,
        actor=request.user,
        request=request,
    )
    if formulario.is_valid():
        formulario.save()
        messages.success(request, "El estado del usuario se actualizó correctamente.")
    else:
        messages.error(request, formulario.errors.as_text())
    return redirect("accounts:usuario_detail", pk=usuario.pk)


@permiso_required("USUARIO_DESACTIVAR")
@require_POST
def usuario_bloquear(request, pk):
    usuario = get_object_or_404(_usuarios_visibles_para(request.user), pk=pk)
    formulario = UsuarioEstadoForm(
        {"estado": EstadoUsuario.BLOQUEADO},
        usuario=usuario,
        actor=request.user,
        request=request,
    )
    if formulario.is_valid():
        formulario.save()
        messages.success(request, "El usuario fue bloqueado.")
    else:
        messages.error(request, formulario.errors.as_text())
    return redirect("accounts:usuario_detail", pk=usuario.pk)


@permiso_required("USUARIO_DESACTIVAR")
@require_POST
def usuario_desbloquear(request, pk):
    usuario = get_object_or_404(_usuarios_visibles_para(request.user), pk=pk)
    formulario = UsuarioEstadoForm(
        {"estado": EstadoUsuario.ACTIVO},
        usuario=usuario,
        actor=request.user,
        request=request,
    )
    if formulario.is_valid():
        formulario.save()
        messages.success(request, "El usuario fue desbloqueado.")
    else:
        messages.error(request, formulario.errors.as_text())
    return redirect("accounts:usuario_detail", pk=usuario.pk)


@permiso_required("USUARIO_EDITAR")
@require_http_methods(["GET", "POST"])
def usuario_cambiar_password(request, pk):
    usuario = get_object_or_404(_usuarios_visibles_para(request.user), pk=pk)
    conservar_session_key = (
        request.session.session_key if usuario.pk == request.user.pk else None
    )
    formulario = UsuarioPasswordForm(
        request.POST or None,
        usuario=usuario,
        actor=request.user,
        request=request,
        conservar_session_key=conservar_session_key,
    )
    if request.method == "POST" and formulario.is_valid():
        usuario_actualizado = formulario.save()
        if usuario.pk == request.user.pk:
            update_session_auth_hash(request, usuario_actualizado)
        messages.success(request, "La contraseña se actualizó correctamente.")
        return redirect("accounts:usuario_detail", pk=usuario.pk)
    return render(
        request,
        "accounts/usuario_password_form.html",
        {
            "form": formulario,
            "usuario_cpos": usuario,
            "page_title": "Cambiar contraseña",
        },
    )


@permiso_required("ROL_VER")
def roles_list(request):
    return render(
        request,
        "accounts/roles_list.html",
        {
            "roles": Rol.objects.all(),
            "page_title": "Roles",
            "active_page": "roles",
        },
    )


@rol_required("supervisor")
@require_http_methods(["GET", "POST"])
def rol_create(request):
    formulario = RolForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            rol = formulario.save()
            _registrar_accion(
                request,
                modulo="seguridad",
                accion="crear_rol",
                tabla_afectada="roles",
                registro_id=rol.pk,
                descripcion="Se creó un rol.",
            )
        messages.success(request, "El rol se creó correctamente.")
        return redirect("accounts:rol_detail", pk=rol.pk)
    return render(
        request,
        "accounts/rol_form.html",
        {"form": formulario, "modo": "crear", "page_title": "Crear rol"},
    )


@rol_required("supervisor")
@require_http_methods(["GET", "POST"])
def rol_update(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    formulario = RolForm(request.POST or None, instance=rol)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            rol = formulario.save()
            _registrar_accion(
                request,
                modulo="seguridad",
                accion="editar_rol",
                tabla_afectada="roles",
                registro_id=rol.pk,
                descripcion="Se actualizó un rol.",
            )
        messages.success(request, "El rol se actualizó correctamente.")
        return redirect("accounts:rol_detail", pk=rol.pk)
    return render(
        request,
        "accounts/rol_form.html",
        {"form": formulario, "rol": rol, "modo": "editar", "page_title": "Editar rol"},
    )


@permiso_required("ROL_VER")
def rol_detail(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    permisos = Permiso.objects.filter(asignaciones_roles__rol=rol).order_by(
        "modulo", "codigo"
    )
    return render(
        request,
        "accounts/rol_detail.html",
        {"rol": rol, "permisos": permisos, "page_title": "Detalle de rol"},
    )


@permiso_required("PERMISO_VER")
def permisos_list(request):
    modulo = request.GET.get("modulo", "").strip()
    consulta = Permiso.objects.all()
    if modulo:
        consulta = consulta.filter(modulo=modulo)
    return render(
        request,
        "accounts/permisos_list.html",
        {
            "permisos": consulta,
            "modulos": Permiso.objects.order_by("modulo").values_list(
                "modulo", flat=True
            ).distinct(),
            "modulo_seleccionado": modulo,
            "page_title": "Permisos",
            "active_page": "permisos",
        },
    )


@rol_required("supervisor")
@require_http_methods(["GET", "POST"])
def permiso_create(request):
    formulario = PermisoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            permiso = formulario.save()
            _registrar_accion(
                request,
                modulo="seguridad",
                accion="crear_permiso",
                tabla_afectada="permisos",
                registro_id=permiso.pk,
                descripcion="Se creó un permiso.",
            )
        messages.success(request, "El permiso se creó correctamente.")
        return redirect("accounts:permisos_list")
    return render(
        request,
        "accounts/permiso_form.html",
        {"form": formulario, "modo": "crear", "page_title": "Crear permiso"},
    )


@rol_required("supervisor")
@require_http_methods(["GET", "POST"])
def permiso_update(request, pk):
    permiso = get_object_or_404(Permiso, pk=pk)
    formulario = PermisoForm(request.POST or None, instance=permiso)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            permiso = formulario.save()
            _registrar_accion(
                request,
                modulo="seguridad",
                accion="editar_permiso",
                tabla_afectada="permisos",
                registro_id=permiso.pk,
                descripcion="Se actualizó un permiso.",
            )
        messages.success(request, "El permiso se actualizó correctamente.")
        return redirect("accounts:permisos_list")
    return render(
        request,
        "accounts/permiso_form.html",
        {
            "form": formulario,
            "permiso": permiso,
            "modo": "editar",
            "page_title": "Editar permiso",
        },
    )


@rol_required("supervisor")
@require_http_methods(["GET", "POST"])
def rol_permisos_update(request, pk):
    rol = get_object_or_404(Rol, pk=pk)
    formulario = RolPermisoForm(request.POST or None, rol=rol)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            formulario.save()
            _registrar_accion(
                request,
                modulo="seguridad",
                accion="asignar_permisos_rol",
                tabla_afectada="rol_permiso",
                registro_id=rol.pk,
                descripcion="Se actualizaron los permisos de un rol.",
            )
        messages.success(request, "Los permisos del rol se actualizaron.")
        return redirect("accounts:rol_detail", pk=rol.pk)
    return render(
        request,
        "accounts/rol_permisos_form.html",
        {"form": formulario, "rol": rol, "page_title": "Permisos del rol"},
    )


@permiso_required("PROGRAMA_VER")
def programas_list(request):
    consulta = _programas_visibles_para(request.user)
    return render(
        request,
        "accounts/programas_list.html",
        {
            "pagina": _paginar(request, consulta),
            "page_title": "Programas",
            "active_page": "programas",
        },
    )


@permiso_required("PROGRAMA_CREAR")
@require_http_methods(["GET", "POST"])
def programa_create(request):
    formulario = ProgramaForm(request.POST or None)
    _limitar_programa_formulario(formulario, request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            programa = formulario.save()
            _registrar_accion(
                request,
                modulo="academico",
                accion="crear_programa",
                tabla_afectada="programas",
                registro_id=programa.pk,
                descripcion="Se creó un programa.",
            )
        messages.success(request, "El programa se creó correctamente.")
        return redirect("accounts:programa_detail", pk=programa.pk)
    return render(
        request,
        "accounts/programa_form.html",
        {"form": formulario, "modo": "crear", "page_title": "Crear programa"},
    )


@permiso_required("PROGRAMA_EDITAR")
@require_http_methods(["GET", "POST"])
def programa_update(request, pk):
    programa = get_object_or_404(_programas_visibles_para(request.user), pk=pk)
    formulario = ProgramaForm(request.POST or None, instance=programa)
    _limitar_programa_formulario(formulario, request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            programa = formulario.save()
            _registrar_accion(
                request,
                modulo="academico",
                accion="editar_programa",
                tabla_afectada="programas",
                registro_id=programa.pk,
                descripcion="Se actualizó un programa.",
            )
        messages.success(request, "El programa se actualizó correctamente.")
        return redirect("accounts:programa_detail", pk=programa.pk)
    return render(
        request,
        "accounts/programa_form.html",
        {
            "form": formulario,
            "programa": programa,
            "modo": "editar",
            "page_title": "Editar programa",
        },
    )


@permiso_required("PROGRAMA_VER")
def programa_detail(request, pk):
    programa = get_object_or_404(_programas_visibles_para(request.user), pk=pk)
    return render(
        request,
        "accounts/programa_detail.html",
        {
            "programa": programa,
            "cohortes": Cohorte.objects.filter(programa=programa),
            "page_title": "Detalle de programa",
        },
    )


@permiso_required("COHORTE_VER")
def cohortes_list(request):
    consulta = _cohortes_visibles_para(request.user)
    programa_id = request.GET.get("programa", "").strip()
    if programa_id.isdigit():
        consulta = consulta.filter(programa_id=int(programa_id))
    return render(
        request,
        "accounts/cohortes_list.html",
        {
            "pagina": _paginar(request, consulta),
            "programas": _programas_visibles_para(request.user),
            "programa_seleccionado": programa_id,
            "page_title": "Cohortes",
            "active_page": "cohortes",
        },
    )


@permiso_required("COHORTE_CREAR")
@require_http_methods(["GET", "POST"])
def cohorte_create(request):
    formulario = CohorteForm(request.POST or None)
    _limitar_cohorte_formulario(formulario, request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            cohorte = formulario.save()
            _registrar_accion(
                request,
                modulo="academico",
                accion="crear_cohorte",
                tabla_afectada="cohortes",
                registro_id=cohorte.pk,
                descripcion="Se creó una cohorte.",
            )
        messages.success(request, "La cohorte se creó correctamente.")
        return redirect("accounts:cohorte_detail", pk=cohorte.pk)
    return render(
        request,
        "accounts/cohorte_form.html",
        {"form": formulario, "modo": "crear", "page_title": "Crear cohorte"},
    )


@permiso_required("COHORTE_EDITAR")
@require_http_methods(["GET", "POST"])
def cohorte_update(request, pk):
    cohorte = get_object_or_404(_cohortes_visibles_para(request.user), pk=pk)
    formulario = CohorteForm(request.POST or None, instance=cohorte)
    _limitar_cohorte_formulario(formulario, request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            cohorte = formulario.save()
            _registrar_accion(
                request,
                modulo="academico",
                accion="editar_cohorte",
                tabla_afectada="cohortes",
                registro_id=cohorte.pk,
                descripcion="Se actualizó una cohorte.",
            )
        messages.success(request, "La cohorte se actualizó correctamente.")
        return redirect("accounts:cohorte_detail", pk=cohorte.pk)
    return render(
        request,
        "accounts/cohorte_form.html",
        {
            "form": formulario,
            "cohorte": cohorte,
            "modo": "editar",
            "page_title": "Editar cohorte",
        },
    )


@permiso_required("COHORTE_VER")
def cohorte_detail(request, pk):
    cohorte = get_object_or_404(_cohortes_visibles_para(request.user), pk=pk)
    return render(
        request,
        "accounts/cohorte_detail.html",
        {
            "cohorte": cohorte,
            "maestrantes": Maestrante.objects.filter(cohorte=cohorte).select_related(
                "usuario"
            ),
            "page_title": "Detalle de cohorte",
        },
    )


@permiso_required("MAESTRANTE_VER")
def maestrantes_list(request):
    consulta = _maestrantes_visibles_para(request.user)
    busqueda = request.GET.get("q", "").strip()
    if busqueda:
        consulta = consulta.filter(
            Q(usuario__nombres__icontains=busqueda)
            | Q(usuario__apellidos__icontains=busqueda)
            | Q(codigo_matricula__icontains=busqueda)
        )
    return render(
        request,
        "accounts/maestrantes_list.html",
        {
            "pagina": _paginar(request, consulta),
            "busqueda": busqueda,
            "page_title": "Maestrantes",
            "active_page": "maestrantes",
        },
    )


@permiso_required("MAESTRANTE_CREAR")
@require_http_methods(["GET", "POST"])
def maestrante_create(request):
    formulario = MaestranteForm(request.POST or None)
    _limitar_maestrante_formulario(formulario, request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            maestrante = formulario.save()
            _registrar_accion(
                request,
                modulo="academico",
                accion="crear_maestrante",
                tabla_afectada="maestrantes",
                registro_id=maestrante.pk,
                descripcion="Se creó un perfil de maestrante.",
            )
        messages.success(request, "El maestrante se registró correctamente.")
        return redirect("accounts:maestrante_detail", pk=maestrante.pk)
    return render(
        request,
        "accounts/maestrante_form.html",
        {"form": formulario, "modo": "crear", "page_title": "Registrar maestrante"},
    )


@permiso_required("MAESTRANTE_EDITAR")
@require_http_methods(["GET", "POST"])
def maestrante_update(request, pk):
    maestrante = get_object_or_404(_maestrantes_visibles_para(request.user), pk=pk)
    formulario = MaestranteForm(request.POST or None, instance=maestrante)
    _limitar_maestrante_formulario(formulario, request.user)
    if request.method == "POST" and formulario.is_valid():
        with transaction.atomic():
            maestrante = formulario.save()
            _registrar_accion(
                request,
                modulo="academico",
                accion="editar_maestrante",
                tabla_afectada="maestrantes",
                registro_id=maestrante.pk,
                descripcion="Se actualizó un perfil de maestrante.",
            )
        messages.success(request, "El maestrante se actualizó correctamente.")
        return redirect("accounts:maestrante_detail", pk=maestrante.pk)
    return render(
        request,
        "accounts/maestrante_form.html",
        {
            "form": formulario,
            "maestrante": maestrante,
            "modo": "editar",
            "page_title": "Editar maestrante",
        },
    )


@permiso_required("MAESTRANTE_VER")
def maestrante_detail(request, pk):
    maestrante = get_object_or_404(_maestrantes_visibles_para(request.user), pk=pk)
    return render(
        request,
        "accounts/maestrante_detail.html",
        {"maestrante": maestrante, "page_title": "Detalle de maestrante"},
    )


@permiso_required("BITACORA_VER")
def bitacora_list(request):
    consulta = Bitacora.objects.select_related("usuario", "usuario__rol")
    if not _es_supervisor(request.user):
        consulta = consulta.filter(usuario=request.user)
    modulos_visibles = consulta.order_by("modulo").values_list(
        "modulo", flat=True
    ).distinct()
    modulo = request.GET.get("modulo", "").strip()
    accion = request.GET.get("accion", "").strip()
    if modulo:
        consulta = consulta.filter(modulo=modulo)
    if accion:
        consulta = consulta.filter(accion__icontains=accion)
    return render(
        request,
        "accounts/bitacora_list.html",
        {
            "pagina": _paginar(request, consulta, por_pagina=30),
            "modulos": modulos_visibles,
            "modulo_seleccionado": modulo,
            "accion": accion,
            "page_title": "Bitácora",
            "active_page": "bitacora",
        },
    )


@rol_required("coordinador", "supervisor")
def verificar_bd(request):
    contexto = {
        "db_ok": False,
        "mensaje": "No fue posible verificar la conexión.",
        "esquema": "cpos",
        "page_title": "Estado de la base de datos",
        "active_page": "db",
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_schema(), 1")
            esquema, resultado = cursor.fetchone()
        contexto["db_ok"] = resultado == 1
        contexto["esquema"] = esquema
        contexto["mensaje"] = (
            "La conexión con PostgreSQL funciona correctamente."
            if contexto["db_ok"]
            else "La conexión respondió con un resultado inesperado."
        )
    except DatabaseError:
        # No se muestran host, credenciales, consultas ni mensajes internos.
        contexto["mensaje"] = "No fue posible conectar con la base de datos."
    return render(request, "accounts/verificar_bd.html", contexto)


def acceso_denegado(request, exception=None):
    return render(
        request,
        "accounts/acceso_denegado.html",
        {
            "page_title": "Acceso denegado",
            "mensaje": "No tiene autorización para acceder a este recurso.",
        },
        status=403,
    )
