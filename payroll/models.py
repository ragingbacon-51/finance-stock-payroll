from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class PayrollRun(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Awaiting approval'
        REJECTED = 'rejected', 'Returned for changes'
        APPROVED = 'approved', 'Approved'
        PAID = 'paid', 'Paid'

    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(9999)]
    )
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    currency_code = models.CharField(
        max_length=3,
        default='',
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{3}$',
                message='Enter a 3-letter uppercase currency code.',
            )
        ],
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='prepared_payroll_runs',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_payroll_runs',
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_payroll_runs',
        null=True,
        blank=True,
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='paid_payroll_runs',
        null=True,
        blank=True,
    )
    review_note = models.CharField(max_length=500, blank=True)
    payment_reference = models.CharField(
        max_length=120,
        unique=True,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-year', '-month', 'currency_code']
        constraints = [
            models.UniqueConstraint(
                fields=['year', 'month', 'currency_code'],
                name='one_payroll_run_per_month_and_currency',
            ),
            models.CheckConstraint(
                condition=Q(month__gte=1, month__lte=12),
                name='payroll_month_in_range',
            ),
            models.CheckConstraint(
                condition=Q(year__gte=2000, year__lte=9999),
                name='payroll_year_in_range',
            ),
        ]
        permissions = [
            ('view_payroll', 'Can view payroll'),
            ('prepare_payroll', 'Can prepare payroll'),
            ('manage_all_payroll', 'Can manage all payroll runs'),
            ('approve_payroll', 'Can approve payroll'),
            ('record_payroll_payment', 'Can record payroll payments'),
        ]

    def __str__(self):
        return (
            f'Payroll {self.year}-{self.month:02d} {self.currency_code} '
            f'({self.get_status_display()})'
        )

    @property
    def period_label(self):
        return f'{self.year}-{self.month:02d}'

    @property
    def total_net_pay(self):
        return sum(
            (line.net_pay for line in self.lines.all()),
            start=0,
        )

    def submit(self):
        if self.status not in (self.Status.DRAFT, self.Status.REJECTED):
            raise ValidationError('Only draft or returned payroll can be submitted.')
        if not self.lines.exists():
            raise ValidationError('Payroll must contain at least one employee.')
        self.status = self.Status.SUBMITTED
        self.review_note = ''
        self.approved_by = None
        self.reviewed_by = None
        self.reviewed_at = None
        self.approved_at = None
        self.submitted_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'review_note',
                'approved_by',
                'reviewed_by',
                'reviewed_at',
                'approved_at',
                'submitted_at',
            ]
        )

    def approve(self, reviewer):
        if self.status != self.Status.SUBMITTED:
            raise ValidationError('Only payroll awaiting approval can be approved.')
        if reviewer.pk == self.prepared_by_id:
            raise ValidationError('The preparer cannot approve their own payroll.')
        self.status = self.Status.APPROVED
        self.approved_by = reviewer
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.approved_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'approved_by',
                'reviewed_by',
                'reviewed_at',
                'approved_at',
            ]
        )

    def reject(self, reviewer, note):
        if self.status != self.Status.SUBMITTED:
            raise ValidationError('Only payroll awaiting approval can be returned.')
        if reviewer.pk == self.prepared_by_id:
            raise ValidationError('The preparer cannot review their own payroll.')
        cleaned_note = note.strip()
        if not cleaned_note:
            raise ValidationError('A reason is required to return payroll.')
        if len(cleaned_note) > 500:
            raise ValidationError('The review note must be 500 characters or fewer.')
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.approved_by = None
        self.reviewed_at = timezone.now()
        self.approved_at = None
        self.review_note = cleaned_note
        self.save(
            update_fields=[
                'status',
                'reviewed_by',
                'approved_by',
                'reviewed_at',
                'approved_at',
                'review_note',
            ]
        )

    def record_payment(self, payer, reference):
        if self.status != self.Status.APPROVED:
            raise ValidationError('Only approved payroll can be marked as paid.')
        cleaned_reference = reference.strip()
        if not cleaned_reference:
            raise ValidationError('A payment reference is required.')
        if len(cleaned_reference) > 120:
            raise ValidationError('The payment reference must be 120 characters or fewer.')
        if PayrollRun.objects.exclude(pk=self.pk).filter(
            payment_reference=cleaned_reference
        ).exists():
            raise ValidationError('That payment reference has already been used.')
        self.status = self.Status.PAID
        self.paid_by = payer
        self.payment_reference = cleaned_reference
        self.paid_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'paid_by',
                'payment_reference',
                'paid_at',
            ]
        )


class PayrollLine(models.Model):
    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.PROTECT,
        related_name='payroll_lines',
    )
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2)
    additions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    adjustment_note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['employee__last_name', 'employee__first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['run', 'employee'],
                name='one_payroll_line_per_employee_per_run',
            ),
            models.CheckConstraint(
                condition=Q(monthly_salary__gt=0),
                name='payroll_line_salary_positive',
            ),
            models.CheckConstraint(
                condition=Q(additions__gte=0),
                name='payroll_line_additions_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(deductions__gte=0),
                name='payroll_line_deductions_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(deductions__lte=F('monthly_salary') + F('additions')),
                name='payroll_line_net_pay_nonnegative',
            ),
            models.CheckConstraint(
                condition=(
                    Q(additions=0, deductions=0)
                    | ~Q(adjustment_note='')
                ),
                name='payroll_adjustments_explained',
            ),
        ]

    @property
    def net_pay(self):
        return self.monthly_salary + self.additions - self.deductions

    def clean(self):
        if (
            self.employee_id
            and self.run_id
            and self.employee.salary_currency != self.run.currency_code
        ):
            raise ValidationError(
                {'employee': 'Employee salary currency must match the payroll run.'}
            )
        if self.deductions > self.monthly_salary + self.additions:
            raise ValidationError(
                {'deductions': 'Deductions cannot exceed salary plus additions.'}
            )
        if self.additions > 0 and not self.adjustment_note.strip():
            raise ValidationError(
                {'adjustment_note': 'Explain the additions or deductions.'}
            )
        if self.deductions > 0 and not self.adjustment_note.strip():
            raise ValidationError(
                {'adjustment_note': 'Explain the additions or deductions.'}
            )
