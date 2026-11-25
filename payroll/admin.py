from django.contrib import admin

from .models import PayrollLine, PayrollRun


class PayrollLineInline(admin.TabularInline):
    model = PayrollLine
    extra = 0
    readonly_fields = [field.name for field in PayrollLine._meta.fields]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = (
        'year',
        'month',
        'currency_code',
        'status',
        'prepared_by',
        'approved_by',
        'paid_at',
    )
    list_filter = ('year', 'month', 'currency_code', 'status')
    readonly_fields = [field.name for field in PayrollRun._meta.fields]
    inlines = [PayrollLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
