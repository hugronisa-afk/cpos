from django.contrib import admin
from django.urls import include, path
from .views import db_status, landing

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing, name='landing'),
    path('estado-db/', db_status, name='db_status'),
    path('', include('apps.accounts.urls')),
    path('titulacion/', include('apps.titulacion.urls')),
    path('seguimiento/', include('apps.seguimiento.urls')),
]
