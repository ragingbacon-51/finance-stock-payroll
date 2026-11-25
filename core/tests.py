from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Finance, Stock and Payroll')


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
