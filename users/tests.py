from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

class UserTests(TestCase):
	def test_register_view_creates_user(self):
		response = self.client.post(reverse('register'), {
			'username': 'testuser',
			'password1': 'strongpassword123',
			'password2': 'strongpassword123',
			'email': 'testuser@example.com'
		})
		self.assertEqual(response.status_code, 302)  # Redirect after successful registration
		self.assertTrue(User.objects.filter(username='testuser').exists())

	def test_register_view_password_mismatch(self):
		response = self.client.post(reverse('register'), {
			'username': 'testuser2',
			'password1': 'password123',
			'password2': 'password456',
			'email': 'testuser2@example.com'
		})
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "The two password fields didn’t match.")

	def test_user_detail_view_authenticated(self):
		user = User.objects.create_user(username='detailuser', password='testpass')
		self.client.login(username='detailuser', password='testpass')
		response = self.client.get(reverse('user-detail', kwargs={'pk': user.pk}))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'detailuser')

	def test_user_detail_view_unauthenticated(self):
		user = User.objects.create_user(username='detailuser2', password='testpass2')
		response = self.client.get(reverse('user-detail', kwargs={'pk': user.pk}))
		self.assertEqual(response.status_code, 302) # Redirect to login

# replace 'register' and 'user-detail' with your actual URL names if different.
