from django.conf import settings
from django.db import connection
from django.shortcuts import render


def landing(request):
    return render(request, 'landing.html')


def db_status(request):
    database = settings.DATABASES.get('default', {})
    context = {
        'page_title': 'Estado de base de datos',
        'page_subtitle': 'Verificación rápida de conexión PostgreSQL',
        'active_page': 'db',
        'db_ok': False,
        'message': 'La conexión todavía no fue verificada.',
        'error_detail': '',
        'db_engine': database.get('ENGINE', 'No configurado'),
        'db_name': database.get('NAME', 'No configurado'),
        'db_host': database.get('HOST', 'localhost') or 'localhost',
        'db_port': database.get('PORT', '5432') or '5432',
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
            result = cursor.fetchone()
        if result and result[0] == 1:
            context['db_ok'] = True
            context['message'] = 'Django pudo conectarse correctamente a la base de datos configurada.'
        else:
            context['message'] = 'La consulta se ejecutó, pero no devolvió el resultado esperado.'
    except Exception as exc:
        context['message'] = 'Django no pudo conectarse a la base de datos configurada.'
        context['error_detail'] = str(exc)

    return render(request, 'db_status.html', context)
