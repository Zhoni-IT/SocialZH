# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, '/home/k/keeperyd/keeperyd.beget.tech/SocialZH/')
sys.path.insert(1, '/home/k/keeperyd/.local/lib/python3.10/site-packages')
os.environ['DJANGO_SETTINGS_MODULE'] = 'SocialZH.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()