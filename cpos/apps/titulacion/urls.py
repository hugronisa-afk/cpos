from django.urls import path
from . import views

app_name = 'titulacion'

urlpatterns = [
    path('', views.dashboard_titulacion, name='dashboard'),
    path('expediente/', views.expediente, name='expediente'),
    path('proyecto/', views.proyecto, name='proyecto'),
    path('articulo/', views.articulo, name='articulo'),
    path('aprobaciones/', views.aprobaciones, name='aprobaciones'),
    path('requerimientos/', views.requerimientos, name='requerimientos'),
]
