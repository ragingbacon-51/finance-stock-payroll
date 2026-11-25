from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from core.models import AuditLog

from .models import Product, StockMovement


@transaction.atomic
def record_stock_movement(*, product_id, movement_type, quantity, reason, user):
    if movement_type not in StockMovement.Type.values:
        raise ValidationError('Choose a valid stock movement type.')
    if quantity < 1:
        raise ValidationError('Quantity must be at least one.')

    product = Product.objects.select_for_update().get(pk=product_id)
    if not product.is_active:
        raise ValidationError('Stock cannot be recorded for an inactive product.')

    totals = StockMovement.objects.filter(product=product).aggregate(
        received=Sum(
            'quantity',
            filter=Q(movement_type=StockMovement.Type.IN),
        ),
        issued=Sum(
            'quantity',
            filter=Q(movement_type=StockMovement.Type.OUT),
        ),
    )
    balance = (totals['received'] or 0) - (totals['issued'] or 0)
    if movement_type == StockMovement.Type.OUT and quantity > balance:
        raise ValidationError(
            f'Only {balance} unit(s) are available; cannot issue {quantity}.'
        )

    movement = StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        reason=reason,
        recorded_by=user,
    )
    AuditLog.objects.create(
        user=user,
        action=f'stock_{movement_type}',
        model_name='StockMovement',
        object_id=movement.pk,
        details=f'{quantity} unit(s) of {product.sku}: {reason}',
    )
    return movement
