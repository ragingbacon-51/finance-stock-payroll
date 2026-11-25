from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'category',
        'amount',
        'occurred_on',
        'status',
        'submitted_by',
        'reviewed_by',
    )
    list_filter = ('status', 'category', 'occurred_on')
    search_fields = ('category', 'description', 'submitted_by__username')
    readonly_fields = [field.name for field in Expense._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
