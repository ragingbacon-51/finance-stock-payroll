from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from core.models import AuditLog

from .forms import ProductForm, StockMovementForm
from .models import Product, StockMovement
from .services import record_stock_movement


def _require_permission(user, permission):
    if not user.has_perm(permission):
        raise PermissionDenied


def _products_with_balance():
    return Product.objects.annotate(
        received=Coalesce(
            Sum(
                'movements__quantity',
                filter=Q(movements__movement_type=StockMovement.Type.IN),
            ),
            Value(0),
            output_field=IntegerField(),
        ),
        issued=Coalesce(
            Sum(
                'movements__quantity',
                filter=Q(movements__movement_type=StockMovement.Type.OUT),
            ),
            Value(0),
            output_field=IntegerField(),
        ),
    ).annotate(balance=F('received') - F('issued'))


@login_required
def stock_list(request):
    _require_permission(request.user, 'inventory.view_stock')
    return render(
        request,
        'inventory/stock_list.html',
        {
            'products': _products_with_balance().filter(is_active=True),
            'can_manage': request.user.has_perm('inventory.manage_stock'),
        },
    )


@login_required
def product_create(request):
    _require_permission(request.user, 'inventory.manage_stock')
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                product = form.save()
                AuditLog.objects.create(
                    user=request.user,
                    action='created',
                    model_name='Product',
                    object_id=product.pk,
                    details=f'Product {product.sku} created.',
                )
            messages.success(request, 'Product created.')
            return redirect('inventory:product_detail', pk=product.pk)
    else:
        form = ProductForm()

    return render(request, 'inventory/product_form.html', {'form': form})


@login_required
def product_detail(request, pk):
    _require_permission(request.user, 'inventory.view_stock')
    product = get_object_or_404(
        _products_with_balance().filter(is_active=True),
        pk=pk,
    )
    return render(
        request,
        'inventory/product_detail.html',
        {
            'product': product,
            'movements': product.movements.select_related('recorded_by'),
            'can_manage': request.user.has_perm('inventory.manage_stock'),
        },
    )


@login_required
def movement_create(request):
    _require_permission(request.user, 'inventory.manage_stock')
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            try:
                movement = record_stock_movement(
                    product_id=form.cleaned_data['product'].pk,
                    movement_type=form.cleaned_data['movement_type'],
                    quantity=form.cleaned_data['quantity'],
                    reason=form.cleaned_data['reason'],
                    user=request.user,
                )
            except ValidationError as error:
                form.add_error('quantity', error)
            else:
                messages.success(request, 'Stock movement recorded.')
                return redirect(
                    'inventory:product_detail',
                    pk=movement.product_id,
                )
    else:
        form = StockMovementForm()

    return render(request, 'inventory/movement_form.html', {'form': form})
