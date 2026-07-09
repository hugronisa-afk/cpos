from django.shortcuts import render


def usuarios(request):
    return render(request, 'accounts/usuarios.html', {
        'page_title': 'Usuarios y roles',
        'page_subtitle': 'Administración de perfiles, programas y cohortes',
        'active_page': 'usuarios',
    })


def auditoria(request):
    return render(request, 'accounts/auditoria.html', {
        'page_title': 'Bitácora de acciones',
        'page_subtitle': 'Registro básico de acciones y trazabilidad del sistema',
        'active_page': 'auditoria',
    })
