from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import verificar_bd

from .views import landing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing, name='landing'),
    path('estado-db/', verificar_bd, name='db_status'),
    path('', include('apps.accounts.urls')),
    path('titulacion/', include('apps.titulacion.urls')),
    path('seguimiento/', include('apps.seguimiento.urls')),
]

handler403 = 'apps.accounts.views.acceso_denegado'
