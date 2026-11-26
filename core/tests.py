from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Finance, Stock and Payroll')

    def test_privacy_notice_is_available_without_login(self):
        response = self.client.get(reverse('privacy'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Draft for development only')
        self.assertContains(response, 'Uploaded receipts are not automatically deleted')
        self.assertContains(response, 'session and CSRF cookies')
        self.assertContains(response, 'mailto:torqueverseke@gmail.com')


class SecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='login-test',
            password='valid-test-password',
            is_staff=True,
        )

    def test_security_headers_and_same_origin_policy(self):
        response = self.client.get(
            reverse('home'),
            HTTP_ORIGIN='https://untrusted.example',
        )

        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_authenticated_pages_are_not_cached(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('expenses:list'))
        self.assertIn('no-store', response['Cache-Control'])

    def test_admin_requires_login_and_staff_access(self):
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_sensitive_local_files_are_not_django_routes(self):
        for path in ('/.env', '/db.sqlite3'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_login_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for url in (reverse('login'), reverse('admin:login')):
            with self.subTest(url=url):
                response = client.post(
                    url,
                    {'username': self.user.username, 'password': 'wrong-password'},
                )
                self.assertEqual(response.status_code, 403)

    def test_failed_logins_are_limited_for_normal_and_admin_login(self):
        for url, ip in (
            (reverse('login'), '192.0.2.1'),
            (reverse('admin:login'), '192.0.2.2'),
        ):
            with self.subTest(url=url):
                for attempt in range(5):
                    response = self.client.post(
                        url,
                        {'username': self.user.username, 'password': 'wrong-password'},
                        REMOTE_ADDR=ip,
                        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                    )
                    if attempt < 4:
                        self.assertEqual(response.status_code, 200)
                self.assertEqual(response.status_code, 429)
                self.assertNotEqual(response.get('Access-Control-Allow-Origin'), '*')
                blocked = self.client.post(
                    url,
                    {'username': self.user.username, 'password': 'valid-test-password'},
                    REMOTE_ADDR=ip,
                )
                self.assertEqual(blocked.status_code, 429)


class SetupRolesCommandTests(TestCase):
    def test_setup_roles_is_repeatable(self):
        call_command('setup_roles')
        call_command('setup_roles')

        self.assertCountEqual(
            Group.objects.values_list('name', flat=True),
            ['Admin', 'Accountant', 'Storekeeper', 'Manager'],
        )
        accountant = Group.objects.get(name='Accountant')
        permission = Permission.objects.get(
            content_type__app_label='expenses',
            codename='review_expense',
        )
        self.assertTrue(accountant.permissions.filter(pk=permission.pk).exists())
        view_stock = Permission.objects.get(
            content_type__app_label='inventory',
            codename='view_stock',
        )
        self.assertTrue(accountant.permissions.filter(pk=view_stock.pk).exists())
        storekeeper = Group.objects.get(name='Storekeeper')
        manage_stock = Permission.objects.get(
            content_type__app_label='inventory',
            codename='manage_stock',
        )
        self.assertTrue(storekeeper.permissions.filter(pk=manage_stock.pk).exists())
        self.assertFalse(accountant.permissions.filter(pk=manage_stock.pk).exists())
        manager = Group.objects.get(name='Manager')
        manage_employees = Permission.objects.get(
            content_type__app_label='hr',
            codename='manage_employees',
        )
        approve_payroll = Permission.objects.get(
            content_type__app_label='payroll',
            codename='approve_payroll',
        )
        prepare_payroll = Permission.objects.get(
            content_type__app_label='payroll',
            codename='prepare_payroll',
        )
        self.assertTrue(manager.permissions.filter(pk=manage_employees.pk).exists())
        self.assertTrue(manager.permissions.filter(pk=approve_payroll.pk).exists())
        self.assertFalse(manager.permissions.filter(pk=prepare_payroll.pk).exists())
        self.assertTrue(accountant.permissions.filter(pk=prepare_payroll.pk).exists())
        self.assertFalse(accountant.permissions.filter(pk=approve_payroll.pk).exists())
