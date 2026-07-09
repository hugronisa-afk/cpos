from django.urls import path
from . import views

app_name = 'seguimiento'

urlpatterns = [
    path('', views.dashboard_seguimiento, name='dashboard'),
    path('tutorias/', views.tutorias, name='tutorias'),
    path('evidencias/', views.evidencias, name='evidencias'),
    path('reportes/', views.reportes, name='reportes'),
]
