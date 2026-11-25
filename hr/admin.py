from django.contrib import admin

from .models import AttendanceRecord, Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_number',
        'first_name',
        'last_name',
        'job_title',
        'is_active',
    )
    list_filter = ('is_active', 'start_date')
    search_fields = ('employee_number', 'first_name', 'last_name', 'email')
    readonly_fields = [field.name for field in Employee._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'employee',
        'status',
        'check_in',
        'check_out',
        'marked_by',
    )
    list_filter = ('date', 'status')
    search_fields = ('employee__employee_number', 'employee__first_name', 'employee__last_name')
    readonly_fields = [field.name for field in AttendanceRecord._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
