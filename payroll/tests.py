from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog
from hr.models import Employee

from .models import PayrollLine, PayrollRun

User = get_user_model()


class PayrollWorkflowTests(TestCase):
    def setUp(self):
        call_command('setup_roles')
        self.accountant = User.objects.create_user(
            username='accountant',
            password='test-password',
        )
        self.accountant.groups.add(Group.objects.get(name='Accountant'))
        self.manager = User.objects.create_user(
            username='manager',
            password='test-password',
        )
        self.manager.groups.add(Group.objects.get(name='Manager'))
        self.employee = Employee.objects.create(
            employee_number='EMP-001',
            first_name='Amina',
            last_name='Otieno',
            job_title='Clerk',
            monthly_salary=Decimal('50000.00'),
            salary_currency='KES',
        )

    def create_run(self, year=2026, month=11, prepared_by=None, currency_code='KES'):
        return PayrollRun.objects.create(
            year=year,
            month=month,
            currency_code=currency_code,
            prepared_by=prepared_by or self.accountant,
        )

    def test_accountant_creates_monthly_draft_from_active_salary(self):
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': 'KES'},
        )

        self.assertEqual(response.status_code, 302)
        run = PayrollRun.objects.get()
        line = run.lines.get()
        self.assertEqual(line.employee, self.employee)
        self.assertEqual(line.monthly_salary, Decimal('50000.00'))
        self.assertEqual(run.status, PayrollRun.Status.DRAFT)
        self.assertEqual(run.currency_code, 'KES')
        detail = self.client.get(reverse('payroll:detail', args=[run.pk]))
        adjustments = self.client.get(reverse('payroll:update', args=[run.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(adjustments.status_code, 200)
        self.assertContains(adjustments, 'Amina Otieno')

    def test_accountant_can_save_explained_adjustments_from_payroll_form(self):
        run = self.create_run()
        line = run.lines.create(
            employee=self.employee,
            monthly_salary=self.employee.monthly_salary,
        )
        self.client.force_login(self.accountant)
        response = self.client.get(reverse('payroll:update', args=[run.pk]))
        self.assertEqual(response.status_code, 200)
        prefix = response.context['formset'].prefix

        response = self.client.post(
            reverse('payroll:update', args=[run.pk]),
            {
                f'{prefix}-TOTAL_FORMS': '1',
                f'{prefix}-INITIAL_FORMS': '1',
                f'{prefix}-MIN_NUM_FORMS': '0',
                f'{prefix}-MAX_NUM_FORMS': '1000',
                f'{prefix}-0-id': str(line.pk),
                f'{prefix}-0-additions': '1500.00',
                f'{prefix}-0-deductions': '250.00',
                f'{prefix}-0-adjustment_note': 'Approved travel allowance and advance.',
            },
        )

        self.assertEqual(response.status_code, 302)
        line.refresh_from_db()
        self.assertEqual(line.additions, Decimal('1500.00'))
        self.assertEqual(line.deductions, Decimal('250.00'))
        self.assertEqual(line.net_pay, Decimal('51250.00'))

    def test_multiple_currencies_have_separate_runs_and_totals(self):
        usd_employee = Employee.objects.create(
            employee_number='EMP-USD',
            first_name='Maya',
            last_name='Ali',
            job_title='Designer',
            monthly_salary=Decimal('1800.00'),
            salary_currency='USD',
        )
        self.client.force_login(self.accountant)
        kes_response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': 'KES'},
        )
        usd_response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': 'usd'},
        )

        self.assertEqual(kes_response.status_code, 302)
        self.assertEqual(usd_response.status_code, 302)
        kes_run = PayrollRun.objects.get(currency_code='KES')
        usd_run = PayrollRun.objects.get(currency_code='USD')
        self.assertEqual(
            list(kes_run.lines.values_list('employee_id', flat=True)),
            [self.employee.pk],
        )
        self.assertEqual(
            list(usd_run.lines.values_list('employee_id', flat=True)),
            [usd_employee.pk],
        )
        self.assertEqual(kes_run.total_net_pay, Decimal('50000.00'))
        self.assertEqual(usd_run.total_net_pay, Decimal('1800.00'))

    def test_payroll_requires_at_least_one_active_employee(self):
        self.employee.is_active = False
        self.employee.save(update_fields=['is_active'])
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': 'KES'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PayrollRun.objects.exists())

    def test_only_accountant_can_prepare_payroll(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('payroll:create'))

        self.assertEqual(response.status_code, 403)

    def test_accountant_can_adjust_net_pay_and_record_payment_after_approval(self):
        self.client.force_login(self.accountant)
        self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': 'KES'},
        )
        run = PayrollRun.objects.get()
        line = run.lines.get()
        line.additions = Decimal('2000.00')
        line.deductions = Decimal('500.00')
        line.adjustment_note = 'Approved transport allowance and advance.'
        line.save()
        self.assertEqual(line.net_pay, Decimal('51500.00'))
        self.assertEqual(run.total_net_pay, Decimal('51500.00'))

        self.client.post(reverse('payroll:submit', args=[run.pk]))
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.SUBMITTED)

        self.client.force_login(self.manager)
        approval = self.client.post(
            reverse('payroll:review', args=[run.pk]),
            {'action': 'approve'},
        )
        self.assertEqual(approval.status_code, 302)
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.APPROVED)
        self.assertEqual(run.approved_by, self.manager)

        self.client.force_login(self.accountant)
        payment = self.client.post(
            reverse('payroll:payment', args=[run.pk]),
            {'payment_reference': 'PAY-2026-11-001'},
        )
        self.assertEqual(payment.status_code, 302)
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.PAID)
        self.assertEqual(run.payment_reference, 'PAY-2026-11-001')
        self.assertEqual(run.paid_by, self.accountant)
        self.assertEqual(
            AuditLog.objects.filter(model_name='PayrollRun').count(),
            4,
        )

    def test_preparer_cannot_approve_their_own_run(self):
        run = self.create_run()
        run.lines.create(employee=self.employee, monthly_salary=self.employee.monthly_salary)
        run.submit()
        self.accountant.user_permissions.add(
            Permission.objects.get(
                content_type__app_label='payroll',
                codename='approve_payroll',
            )
        )
        self.client.force_login(self.accountant)

        self.client.post(
            reverse('payroll:review', args=[run.pk]),
            {'action': 'approve'},
        )

        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.SUBMITTED)
        self.assertIsNone(run.approved_by)
        self.assertFalse(
            AuditLog.objects.filter(
                model_name='PayrollRun',
                action='approved',
            ).exists()
        )

    def test_return_requires_a_reason_and_can_be_resubmitted(self):
        run = self.create_run()
        run.lines.create(employee=self.employee, monthly_salary=self.employee.monthly_salary)
        run.submit()
        self.client.force_login(self.manager)

        self.client.post(
            reverse('payroll:review', args=[run.pk]),
            {'action': 'reject', 'review_note': '  '},
        )
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.SUBMITTED)

        self.client.post(
            reverse('payroll:review', args=[run.pk]),
            {'action': 'reject', 'review_note': 'Please verify the adjustment.'},
        )
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.REJECTED)
        self.assertEqual(run.review_note, 'Please verify the adjustment.')
        self.assertIsNotNone(run.reviewed_at)
        self.assertIsNone(run.approved_at)

        self.client.force_login(self.accountant)
        self.client.post(reverse('payroll:submit', args=[run.pk]))
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.SUBMITTED)
        self.assertEqual(run.review_note, '')
        self.assertIsNone(run.reviewed_by)

    def test_net_pay_cannot_be_negative_and_adjustments_need_explanation(self):
        run = self.create_run()
        line = PayrollLine(
            run=run,
            employee=self.employee,
            monthly_salary=Decimal('50000.00'),
            deductions=Decimal('50001.00'),
        )
        with self.assertRaises(ValidationError):
            line.full_clean()

        line.deductions = Decimal('100.00')
        with self.assertRaises(ValidationError):
            line.full_clean()

    def test_duplicate_payroll_period_is_rejected(self):
        self.create_run()
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': 'KES'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PayrollRun.objects.count(), 1)

    def test_cannot_edit_or_pay_payroll_in_invalid_status(self):
        run = self.create_run()
        run.lines.create(employee=self.employee, monthly_salary=self.employee.monthly_salary)
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:payment', args=[run.pk]),
            {'payment_reference': 'REF-1'},
        )

        self.assertEqual(response.status_code, 302)
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.DRAFT)
        self.assertFalse(run.payment_reference)

    def test_payment_reference_cannot_be_reused(self):
        first_run = self.create_run(month=10)
        first_run.lines.create(
            employee=self.employee,
            monthly_salary=self.employee.monthly_salary,
        )
        first_run.submit()
        first_run.approve(self.manager)
        first_run.record_payment(self.accountant, 'SHARED-REF')

        second_run = self.create_run(month=11)
        second_run.lines.create(
            employee=self.employee,
            monthly_salary=self.employee.monthly_salary,
        )
        second_run.submit()
        second_run.approve(self.manager)
        with self.assertRaises(ValidationError):
            second_run.record_payment(self.accountant, 'SHARED-REF')

        second_run.refresh_from_db()
        self.assertEqual(second_run.status, PayrollRun.Status.APPROVED)
        self.assertIsNone(second_run.payment_reference)

    def test_payroll_month_must_be_valid(self):
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '13', 'currency_code': 'KES'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PayrollRun.objects.exists())

    def test_payroll_currency_code_requires_three_letters(self):
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:create'),
            {'year': '2026', 'month': '11', 'currency_code': '12$'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PayrollRun.objects.exists())

    def test_accountant_cannot_approve_without_manager_permission(self):
        run = self.create_run()
        run.lines.create(employee=self.employee, monthly_salary=self.employee.monthly_salary)
        run.submit()
        self.client.force_login(self.accountant)

        response = self.client.post(
            reverse('payroll:review', args=[run.pk]),
            {'action': 'approve'},
        )

        self.assertEqual(response.status_code, 403)
