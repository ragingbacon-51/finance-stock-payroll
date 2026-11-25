from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db.models import Q


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    reorder_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'sku']
        permissions = [('view_stock', 'Can view stock')]

    def __str__(self):
        return f'{self.sku} - {self.name}'


class StockMovement(models.Model):
    class Type(models.TextChoices):
        IN = 'in', 'Stock received'
        OUT = 'out', 'Stock issued'

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='movements',
    )
    movement_type = models.CharField(max_length=3, choices=Type.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reason = models.CharField(max_length=250)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('manage_stock', 'Can manage stock')]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name='stock_movement_quantity_positive',
            ),
        ]

    def __str__(self):
        return f'{self.get_movement_type_display()}: {self.product} x {self.quantity}'
