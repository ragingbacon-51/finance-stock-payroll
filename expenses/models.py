from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def expense_receipt_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f'expense_receipts/{uuid4().hex}{extension}'


class Expense(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    category = models.CharField(max_length=80)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    occurred_on = models.DateField(default=timezone.localdate)
    receipt = models.FileField(
        upload_to=expense_receipt_upload_to,
        blank=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_expenses',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_expenses',
        null=True,
        blank=True,
    )
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('review_expense', 'Can review expenses')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='expense_amount_positive',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='expense_amount_positive',
            ),
        ]

    def __str__(self):
        return f'{self.category}: {self.amount} ({self.get_status_display()})'

    def approve(self, reviewer, note=''):
        self._validate_review(reviewer)
        cleaned_note = note.strip()
        if len(cleaned_note) > 500:
            raise ValidationError('The review note must be 500 characters or fewer.')
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewer
        self.review_note = cleaned_note
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'reviewed_by',
                'review_note',
                'reviewed_at',
            ]
        )

    def reject(self, reviewer, note):
        self._validate_review(reviewer)
        cleaned_note = note.strip()
        if not cleaned_note:
            raise ValidationError('A reason is required to reject an expense.')
        if len(cleaned_note) > 500:
            raise ValidationError('The review note must be 500 characters or fewer.')

        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.review_note = cleaned_note
        self.reviewed_at = timezone.now()
        self.save(
            update_fields=[
                'status',
                'reviewed_by',
                'review_note',
                'reviewed_at',
            ]
        )

    def _validate_review(self, reviewer):
        if self.status != self.Status.PENDING:
            raise ValidationError('Only pending expenses can be reviewed.')
        if reviewer.pk == self.submitted_by_id:
            raise ValidationError('You cannot review your own expense.')
