# -*- coding: utf-8 -*-
import os
import sys

# Добавляем путь к проекту в sys.path
sys.path.insert(0, '/home/a/akyldyti/akyldyti.beget.tech')  # Замени на свой путь

# Устанавливаем настройки Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SocialZH.settings')

# Получаем WSGI-приложение
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()