from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog

from .models import AttendanceRecord, Employee

User = get_user_model()


class HumanResourcesWorkflowTests(TestCase):
    def setUp(self):
        call_command('setup_roles')
        self.manager = User.objects.create_user(
            username='manager',
            password='test-password',
        )
        self.manager.groups.add(Group.objects.get(name='Manager'))
        self.accountant = User.objects.create_user(
            username='accountant',
            password='test-password',
        )
        self.accountant.groups.add(Group.objects.get(name='Accountant'))
        self.employee = Employee.objects.create(
            employee_number='EMP-001',
            first_name='Amina',
            last_name='Otieno',
            job_title='Clerk',
            monthly_salary='45000.00',
            salary_currency='KES',
        )

    def test_manager_can_add_employee_and_salary_is_saved(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('hr:employee_create'),
            {
                'employee_number': 'EMP-002',
                'first_name': 'Brian',
                'last_name': 'Ouma',
                'email': 'brian@example.test',
                'phone': '0700000000',
                'job_title': 'Assistant',
                'start_date': '2026-10-01',
                'monthly_salary': '52000.00',
                'salary_currency': 'kes',
                'user': '',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        employee = Employee.objects.get(employee_number='EMP-002')
        self.assertEqual(str(employee.monthly_salary), '52000.00')
        self.assertEqual(employee.salary_currency, 'KES')
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='Employee',
                action='created',
                object_id=employee.pk,
            ).exists()
        )

    def test_employee_currency_code_requires_three_letters(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('hr:employee_create'),
            {
                'employee_number': 'EMP-BAD',
                'first_name': 'Invalid',
                'last_name': 'Currency',
                'job_title': 'Assistant',
                'start_date': '2026-10-01',
                'monthly_salary': '100.00',
                'salary_currency': '1$A',
                'user': '',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Employee.objects.filter(employee_number='EMP-BAD').exists())

    def test_accountant_can_view_employees_but_cannot_manage_them(self):
        self.client.force_login(self.accountant)

        list_response = self.client.get(reverse('hr:employees'))
        create_response = self.client.get(reverse('hr:employee_create'))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'KES 45000.00')
        self.assertEqual(create_response.status_code, 403)

    def test_manager_can_record_attendance_with_optional_clock_times(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('hr:attendance_create'),
            {
                'employee': self.employee.pk,
                'date': '2026-11-20',
                'status': AttendanceRecord.Status.PRESENT,
                'check_in': '',
                'check_out': '',
                'note': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get()
        self.assertEqual(record.status, AttendanceRecord.Status.PRESENT)
        self.assertIsNone(record.check_in)

    def test_manager_can_record_attendance_with_clock_in_and_out(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('hr:attendance_create'),
            {
                'employee': self.employee.pk,
                'date': '2026-11-20',
                'status': AttendanceRecord.Status.PRESENT,
                'check_in': '08:00',
                'check_out': '17:00',
                'note': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AttendanceRecord.objects.get().check_in.isoformat(), '08:00:00')
        self.assertEqual(AttendanceRecord.objects.get().check_out.isoformat(), '17:00:00')

    def test_attendance_requires_both_clock_times_and_forbids_reverse_order(self):
        self.client.force_login(self.manager)
        url = reverse('hr:attendance_create')
        data = {
            'employee': self.employee.pk,
            'date': '2026-11-20',
            'status': AttendanceRecord.Status.PRESENT,
            'check_in': '08:00',
            'check_out': '',
            'note': '',
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.exists())

        data['check_out'] = '07:00'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_absence_cannot_have_clock_times(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('hr:attendance_create'),
            {
                'employee': self.employee.pk,
                'date': '2026-11-20',
                'status': AttendanceRecord.Status.ABSENT,
                'check_in': '08:00',
                'check_out': '17:00',
                'note': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_duplicate_daily_attendance_is_rejected(self):
        AttendanceRecord.objects.create(
            employee=self.employee,
            date='2026-11-20',
            status=AttendanceRecord.Status.PRESENT,
            marked_by=self.manager,
        )
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('hr:attendance_create'),
            {
                'employee': self.employee.pk,
                'date': '2026-11-20',
                'status': AttendanceRecord.Status.ABSENT,
                'check_in': '',
                'check_out': '',
                'note': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_attendance_correction_is_audited(self):
        record = AttendanceRecord.objects.create(
            employee=self.employee,
            date='2026-11-20',
            status=AttendanceRecord.Status.ABSENT,
            marked_by=self.manager,
        )
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('hr:attendance_update', args=[record.pk]),
            {
                'employee': self.employee.pk,
                'date': '2026-11-20',
                'status': AttendanceRecord.Status.PRESENT,
                'check_in': '08:00',
                'check_out': '17:00',
                'note': 'Correction approved.',
            },
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, AttendanceRecord.Status.PRESENT)
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='AttendanceRecord',
                action='corrected',
                object_id=record.pk,
            ).exists()
        )

    def test_accountant_can_view_attendance_but_cannot_change_it(self):
        self.client.force_login(self.accountant)

        list_response = self.client.get(reverse('hr:attendance'))
        create_response = self.client.get(reverse('hr:attendance_create'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 403)

    def test_invalid_attendance_filter_does_not_break_list(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('hr:attendance'),
            {'date': 'not-a-date'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid date.')
