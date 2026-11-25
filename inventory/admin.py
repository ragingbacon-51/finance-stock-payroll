from django.contrib import admin

from .models import Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'reorder_level', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('sku', 'name')
    readonly_fields = ('sku', 'name', 'reorder_level', 'is_active', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'movement_type',
        'quantity',
        'reason',
        'recorded_by',
        'created_at',
    )
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__sku', 'product__name', 'reason', 'recorded_by__username')
    readonly_fields = [field.name for field in StockMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
