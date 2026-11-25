from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog

from .models import Product, StockMovement

User = get_user_model()


class StockWorkflowTests(TestCase):
    def setUp(self):
        call_command('setup_roles')
        self.storekeeper = User.objects.create_user(
            username='storekeeper',
            password='test-password',
        )
        self.storekeeper.groups.add(Group.objects.get(name='Storekeeper'))
        self.accountant = User.objects.create_user(
            username='accountant',
            password='test-password',
        )
        self.accountant.groups.add(Group.objects.get(name='Accountant'))
        self.product = Product.objects.create(
            sku='PEN-001',
            name='Ballpoint pen',
            reorder_level=5,
        )

    def record_movement(self, movement_type, quantity, product=None):
        return self.client.post(
            reverse('inventory:movement_create'),
            {
                'product': (product or self.product).pk,
                'movement_type': movement_type,
                'quantity': quantity,
                'reason': 'Stock count',
            },
        )

    def test_storekeeper_can_receive_and_issue_stock(self):
        self.client.force_login(self.storekeeper)

        receive_response = self.record_movement(StockMovement.Type.IN, '10')
        issue_response = self.record_movement(StockMovement.Type.OUT, '7')

        self.assertEqual(receive_response.status_code, 302)
        self.assertEqual(issue_response.status_code, 302)
        self.assertEqual(
            StockMovement.objects.filter(product=self.product).count(),
            2,
        )
        self.assertEqual(
            AuditLog.objects.filter(model_name='StockMovement').count(),
            2,
        )
        response = self.client.get(reverse('inventory:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['products'][0].balance, 3)

    def test_cannot_issue_more_than_available_stock(self):
        self.client.force_login(self.storekeeper)
        self.record_movement(StockMovement.Type.IN, '4')

        response = self.record_movement(StockMovement.Type.OUT, '5')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            StockMovement.objects.filter(product=self.product).count(),
            1,
        )
        self.assertEqual(
            AuditLog.objects.filter(action='stock_out').count(),
            0,
        )

    def test_accountant_can_view_stock_but_cannot_record_movements(self):
        self.client.force_login(self.accountant)

        list_response = self.client.get(reverse('inventory:list'))
        movement_response = self.client.get(
            reverse('inventory:movement_create')
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(movement_response.status_code, 403)

    def test_storekeeper_can_add_product(self):
        self.client.force_login(self.storekeeper)

        response = self.client.post(
            reverse('inventory:product_create'),
            {
                'sku': 'PEN-002',
                'name': 'Gel pen',
                'reorder_level': '8',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(sku='PEN-002').exists())
        self.assertTrue(AuditLog.objects.filter(model_name='Product').exists())

    def test_user_without_stock_role_cannot_view_stock(self):
        employee = User.objects.create_user(
            username='employee',
            password='test-password',
        )
        self.client.force_login(employee)

        response = self.client.get(reverse('inventory:list'))

        self.assertEqual(response.status_code, 403)
