from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


class Employee(models.Model):
    employee_number = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=100)
    start_date = models.DateField(default=timezone.localdate)
    monthly_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    salary_currency = models.CharField(
        max_length=3,
        default='',
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{3}$',
                message='Enter a 3-letter uppercase currency code.',
            )
        ],
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='employee_profile',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name', 'employee_number']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monthly_salary__gt=0),
                name='employee_monthly_salary_positive',
            ),
        ]
        permissions = [
            ('manage_employees', 'Can manage employees'),
            ('view_attendance', 'Can view attendance records'),
            ('manage_attendance', 'Can manage attendance records'),
        ]

    def __str__(self):
        return f'{self.employee_number} - {self.first_name} {self.last_name}'


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LEAVE = 'leave', 'Leave'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='attendance_records',
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='marked_attendance_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'employee__last_name', 'employee__first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'date'],
                name='one_attendance_record_per_employee_per_day',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(check_in__isnull=True, check_out__isnull=True)
                    | models.Q(check_in__isnull=False, check_out__isnull=False)
                ),
                name='attendance_clock_times_paired',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(check_in__isnull=True)
                    | models.Q(check_in__lt=models.F('check_out'))
                ),
                name='attendance_clock_out_after_clock_in',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='present')
                    | models.Q(check_in__isnull=True, check_out__isnull=True)
                ),
                name='attendance_nonpresent_has_no_clock_times',
            ),
        ]

    def __str__(self):
        return f'{self.employee} - {self.date} ({self.get_status_display()})'

    def clean(self):
        if bool(self.check_in) != bool(self.check_out):
            raise ValidationError(
                'Enter both clock-in and clock-out times, or leave both blank.'
            )
        if self.status != self.Status.PRESENT and (self.check_in or self.check_out):
            raise ValidationError(
                'Clock-in and clock-out times can only be recorded for present staff.'
            )
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError('Clock-out must be later than clock-in.')
