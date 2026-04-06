from django.test import Client
from accounts.models import CustomUser

username = 'testuser'
password = 'testpass123'
try:
    user = CustomUser.objects.get(username=username)
except CustomUser.DoesNotExist:
    user = CustomUser.objects.create_user(username=username, email='test@example.com', password=password)

c = Client()
print('logged', c.login(username=username, password=password))
resp = c.post('/messages/send/bot/', {'content': 'Привет бот'})
print('status', resp.status_code, 'content', resp.content)
print('json', resp.json() if resp.status_code == 200 else 'no json')
resp2 = c.post(f'/messages/send/{user.id}/', {'content': 'Привет'})
print('status2', resp2.status_code, 'content2', resp2.content)
print('json2', resp2.json() if resp2.status_code == 200 else 'no json')
