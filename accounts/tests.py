from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Post, Hashtag

User = get_user_model()

class ProfileTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.post = Post.objects.create(user=self.user1, caption='Test post #demo')

    def test_profile_view_own(self):
        self.client.login(username='user1', password='pass')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user1')
        self.assertTrue(response.context['is_owner'])

    def test_profile_view_other(self):
        self.client.login(username='user1', password='pass')
        response = self.client.get(reverse('profile_view', kwargs={'username': 'user2'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user2')
        self.assertFalse(response.context['is_owner'])

    def test_profile_view_not_found(self):
        self.client.login(username='user1', password='pass')
        response = self.client.get(reverse('profile_view', kwargs={'username': 'nonexistent'}))
        self.assertEqual(response.status_code, 404)

class SearchTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.hashtag = Hashtag.objects.create(name='demo')
        self.post = Post.objects.create(user=self.user, caption='Post with #demo')

    def test_search_hashtag(self):
        response = self.client.get(reverse('search') + '?q=#demo')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'demo')
        self.assertIn(self.post, response.context['posts'])

    def test_search_username(self):
        response = self.client.get(reverse('search') + '?q=testuser')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')
        self.assertIn(self.user, response.context['profiles'])

    def test_search_no_results(self):
        response = self.client.get(reverse('search') + '?q=nonexistent')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ничего не найдено')