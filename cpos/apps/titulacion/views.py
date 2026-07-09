from django.shortcuts import render


def _render(request, template_name, page_title, page_subtitle, active_page):
    return render(request, template_name, {
        'page_title': page_title,
        'page_subtitle': page_subtitle,
        'active_page': active_page,
    })


def dashboard_titulacion(request):
    return _render(
        request,
        'titulacion/dashboard.html',
        'Panel principal',
        'Indicadores generales del proceso de titulación',
        'dashboard',
    )


def expediente(request):
    return _render(request, 'titulacion/expediente.html', 'Expediente', 'Datos principales del maestrante, programa, cohorte y tutor', 'expediente')


def proyecto(request):
    return _render(request, 'titulacion/proyecto.html', 'Proyecto de titulación', 'Tema, modalidad, documentos y solicitudes de cambio', 'proyecto')


def articulo(request):
    return _render(request, 'titulacion/articulo.html', 'Artículo científico', 'Construcción progresiva del artículo por secciones', 'articulo')


def aprobaciones(request):
    return _render(request, 'titulacion/aprobaciones.html', 'Aprobaciones', 'Solicitudes, revisión formal y acciones críticas', 'aprobaciones')


def requerimientos(request):
    return _render(request, 'titulacion/requerimientos.html', 'Requerimientos', 'Listado base de requerimientos funcionales y no funcionales', 'requerimientos')
