from django.shortcuts import render


def _render(request, template_name, page_title, page_subtitle, active_page):
    return render(request, template_name, {
        'page_title': page_title,
        'page_subtitle': page_subtitle,
        'active_page': active_page,
    })


def dashboard_seguimiento(request):
    return _render(
        request,
        'seguimiento/dashboard.html',
        'Panel de seguimiento',
        'Tutorías, evidencias, observaciones, historial y reportes',
        'seguimiento_dashboard',
    )


def tutorias(request):
    return _render(request, 'seguimiento/tutorias.html', 'Tutorías', 'Agenda, asistencia, reprogramaciones y grabaciones', 'tutorias')


def evidencias(request):
    return _render(request, 'seguimiento/evidencias.html', 'Evidencias', 'Carga, versiones, validación y observaciones del tutor', 'evidencias')


def reportes(request):
    return _render(request, 'seguimiento/reportes.html', 'Reportes', 'Indicadores para coordinación y supervisión general', 'reportes')
