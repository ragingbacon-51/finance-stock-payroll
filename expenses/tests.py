from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import AuditLog

from .models import Expense

User = get_user_model()


class ExpenseWorkflowTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

        call_command('setup_roles')
        self.submitter = User.objects.create_user(
            username='submitter',
            password='test-password',
        )
        self.reviewer = User.objects.create_user(
            username='reviewer',
            password='test-password',
        )
        self.reviewer.groups.add(Group.objects.get(name='Accountant'))

    def create_expense(self, submitter=None):
        return Expense.objects.create(
            category='Transport',
            description='Delivery fare',
            amount=Decimal('1200.00'),
            submitted_by=submitter or self.submitter,
        )

    def test_submitter_can_submit_and_download_private_receipt(self):
        self.client.force_login(self.submitter)
        receipt = SimpleUploadedFile(
            'receipt.png',
            b'\x89PNG\r\n\x1a\nreceipt data',
            content_type='image/png',
        )
        response = self.client.post(
            reverse('expenses:create'),
            {
                'category': 'Transport',
                'description': 'Delivery fare',
                'amount': '1200.00',
                'occurred_on': '2026-01-15',
                'receipt': receipt,
            },
        )

        self.assertEqual(response.status_code, 302)
        expense = Expense.objects.get()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertEqual(expense.submitted_by, self.submitter)
        self.assertNotIn('receipt.png', expense.receipt.name)
        self.assertEqual(AuditLog.objects.filter(action='submitted').count(), 1)

        download = self.client.get(
            reverse('expenses:receipt', args=[expense.pk])
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', download['Content-Disposition'])
        download.close()

    def test_other_submitter_cannot_view_expense_or_receipt(self):
        expense = self.create_expense()
        receipt = SimpleUploadedFile(
            'receipt.pdf',
            b'%PDF-1.4 receipt data',
            content_type='application/pdf',
        )
        expense.receipt.save('receipt.pdf', receipt)
        other_user = User.objects.create_user(
            username='other',
            password='test-password',
        )
        self.client.force_login(other_user)

        self.assertEqual(
            self.client.get(reverse('expenses:detail', args=[expense.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse('expenses:receipt', args=[expense.pk])).status_code,
            404,
        )

    def test_reviewer_can_approve_and_audit_expense(self):
        expense = self.create_expense()
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('expenses:review', args=[expense.pk]),
            {'action': 'approve', 'review_note': 'Receipt checked.'},
        )

        self.assertEqual(response.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        self.assertEqual(expense.reviewed_by, self.reviewer)
        self.assertEqual(expense.review_note, 'Receipt checked.')
        self.assertEqual(AuditLog.objects.filter(action='approved').count(), 1)

    def test_submitter_cannot_approve_own_expense(self):
        expense = self.create_expense()
        self.submitter.groups.add(Group.objects.get(name='Accountant'))
        self.client.force_login(self.submitter)

        response = self.client.post(
            reverse('expenses:review', args=[expense.pk]),
            {'action': 'approve'},
        )

        self.assertEqual(response.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertIsNone(expense.reviewed_by)
        self.assertFalse(AuditLog.objects.filter(action='approved').exists())

    def test_rejection_requires_a_reason(self):
        expense = self.create_expense()
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('expenses:review', args=[expense.pk]),
            {'action': 'reject', 'review_note': '   '},
        )

        self.assertEqual(response.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertFalse(AuditLog.objects.filter(action='rejected').exists())

    def test_non_reviewer_cannot_review_expense(self):
        expense = self.create_expense()
        self.client.force_login(self.submitter)

        response = self.client.post(
            reverse('expenses:review', args=[expense.pk]),
            {'action': 'approve'},
        )

        self.assertEqual(response.status_code, 403)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)

    def test_submitter_sees_own_expense_list(self):
        self.create_expense()
        other_user = User.objects.create_user(
            username='other',
            password='test-password',
        )
        self.create_expense(submitter=other_user)
        self.client.force_login(self.submitter)
        response = self.client.get(reverse('expenses:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delivery fare')
        self.assertNotContains(response, 'other')

    def test_expense_text_is_escaped_in_the_list_and_detail(self):
        expense = self.create_expense()
        expense.description = '<script>alert("xss")</script>'
        expense.save(update_fields=['description'])
        self.client.force_login(self.submitter)

        for url in (
            reverse('expenses:list'),
            reverse('expenses:detail', args=[expense.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, '<script>alert("xss")</script>')
                self.assertContains(response, '&lt;script&gt;')

    def test_reviewer_can_open_an_expense_detail(self):
        expense = self.create_expense()
        self.client.force_login(self.reviewer)

        response = self.client.get(
            reverse('expenses:detail', args=[expense.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delivery fare')

    def test_reviewer_can_reject_with_reason(self):
        expense = self.create_expense()
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('expenses:review', args=[expense.pk]),
            {'action': 'reject', 'review_note': 'Missing approval.'},
        )

        self.assertEqual(response.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.REJECTED)
        self.assertEqual(expense.review_note, 'Missing approval.')
        self.assertEqual(AuditLog.objects.filter(action='rejected').count(), 1)

    def test_invalid_receipt_signature_is_rejected(self):
        self.client.force_login(self.submitter)
        response = self.client.post(
            reverse('expenses:create'),
            {
                'category': 'Transport',
                'description': 'Delivery fare',
                'amount': '1200.00',
                'occurred_on': '2026-01-15',
                'receipt': SimpleUploadedFile(
                    'receipt.png',
                    b'not a png',
                    content_type='image/png',
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Expense.objects.exists())
