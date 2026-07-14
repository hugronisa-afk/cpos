"""Rutas de autenticacion y administracion institucional."""

from django.urls import path

from . import views


app_name = "accounts"

urlpatterns = [
    # Autenticacion, panel y perfil.
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path(
        "dashboard/accounts/",
        views.dashboard_accounts,
        name="dashboard_accounts",
    ),
    path("perfil/", views.perfil_usuario, name="perfil"),

    # Usuarios.
    path("usuarios/", views.usuarios_list, name="usuarios"),
    path("usuarios/crear/", views.usuario_create, name="usuario_create"),
    path("usuarios/<int:pk>/", views.usuario_detail, name="usuario_detail"),
    path(
        "usuarios/<int:pk>/editar/",
        views.usuario_update,
        name="usuario_update",
    ),
    path(
        "usuarios/<int:pk>/estado/",
        views.usuario_toggle_estado,
        name="usuario_toggle_estado",
    ),
    path(
        "usuarios/<int:pk>/bloquear/",
        views.usuario_bloquear,
        name="usuario_bloquear",
    ),
    path(
        "usuarios/<int:pk>/desbloquear/",
        views.usuario_desbloquear,
        name="usuario_desbloquear",
    ),
    path(
        "usuarios/<int:pk>/password/",
        views.usuario_cambiar_password,
        name="usuario_cambiar_password",
    ),

    # Roles y permisos.
    path("roles/", views.roles_list, name="roles_list"),
    path("roles/crear/", views.rol_create, name="rol_create"),
    path("roles/<int:pk>/", views.rol_detail, name="rol_detail"),
    path("roles/<int:pk>/editar/", views.rol_update, name="rol_update"),
    path(
        "roles/<int:pk>/permisos/",
        views.rol_permisos_update,
        name="rol_permisos_update",
    ),
    path("permisos/", views.permisos_list, name="permisos_list"),
    path("permisos/crear/", views.permiso_create, name="permiso_create"),
    path(
        "permisos/<int:pk>/editar/",
        views.permiso_update,
        name="permiso_update",
    ),

    # Programas, cohortes y maestrantes.
    path("programas/", views.programas_list, name="programas_list"),
    path("programas/crear/", views.programa_create, name="programa_create"),
    path("programas/<int:pk>/", views.programa_detail, name="programa_detail"),
    path(
        "programas/<int:pk>/editar/",
        views.programa_update,
        name="programa_update",
    ),
    path("cohortes/", views.cohortes_list, name="cohortes_list"),
    path("cohortes/crear/", views.cohorte_create, name="cohorte_create"),
    path("cohortes/<int:pk>/", views.cohorte_detail, name="cohorte_detail"),
    path(
        "cohortes/<int:pk>/editar/",
        views.cohorte_update,
        name="cohorte_update",
    ),
    path("maestrantes/", views.maestrantes_list, name="maestrantes_list"),
    path(
        "maestrantes/crear/",
        views.maestrante_create,
        name="maestrante_create",
    ),
    path(
        "maestrantes/<int:pk>/",
        views.maestrante_detail,
        name="maestrante_detail",
    ),
    path(
        "maestrantes/<int:pk>/editar/",
        views.maestrante_update,
        name="maestrante_update",
    ),

    # Auditoria. La ruta antigua se conserva para no romper enlaces existentes.
    path("bitacora/", views.bitacora_list, name="bitacora_list"),
    path("auditoria/", views.bitacora_list, name="auditoria"),
    path("verificar-bd/", views.verificar_bd, name="verificar_bd"),
    path("acceso-denegado/", views.acceso_denegado, name="acceso_denegado"),
]
