from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.models import AuditLog

from .forms import AttendanceFilterForm, AttendanceForm, EmployeeForm
from .models import AttendanceRecord, Employee


def _require_permission(user, permission):
    if not user.has_perm(permission):
        raise PermissionDenied


@login_required
def employee_list(request):
    _require_permission(request.user, 'hr.view_employee')
    return render(
        request,
        'hr/employee_list.html',
        {
            'employees': Employee.objects.all(),
            'can_manage': request.user.has_perm('hr.manage_employees'),
        },
    )


@login_required
def employee_create(request):
    _require_permission(request.user, 'hr.manage_employees')
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    employee = form.save()
                    AuditLog.objects.create(
                        user=request.user,
                        action='created',
                        model_name='Employee',
                        object_id=employee.pk,
                        details=f'Employee {employee.employee_number} created.',
                    )
            except IntegrityError:
                form.add_error(
                    'employee_number',
                    'An employee with that number or user account already exists.',
                )
            else:
                messages.success(request, 'Employee record created.')
                return redirect('hr:employees')
    else:
        form = EmployeeForm()

    return render(request, 'hr/employee_form.html', {'form': form, 'editing': False})


@login_required
def employee_update(request, pk):
    _require_permission(request.user, 'hr.manage_employees')
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            old_values = {
                field: getattr(employee, field)
                for field in (
                    'employee_number',
                    'first_name',
                    'last_name',
                    'email',
                    'phone',
                    'job_title',
                    'start_date',
                    'monthly_salary',
                    'is_active',
                    'user_id',
                )
            }
            try:
                with transaction.atomic():
                    employee = form.save()
                    changed_fields = [
                        field
                        for field, old_value in old_values.items()
                        if old_value != getattr(employee, field)
                    ]
                    AuditLog.objects.create(
                        user=request.user,
                        action='updated',
                        model_name='Employee',
                        object_id=employee.pk,
                        details=f'Employee {employee.employee_number} fields changed: '
                        f'{", ".join(changed_fields) or "none"}.',
                    )
            except IntegrityError:
                form.add_error(
                    'user',
                    'That user account is already linked to another employee.',
                )
            else:
                messages.success(request, 'Employee record updated.')
                return redirect('hr:employees')
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'hr/employee_form.html', {'form': form, 'editing': True})


@login_required
def attendance_list(request):
    _require_permission(request.user, 'hr.view_attendance')
    records = AttendanceRecord.objects.select_related(
        'employee',
        'marked_by',
    )
    filter_form = AttendanceFilterForm(request.GET or None)
    if filter_form.is_valid() and filter_form.cleaned_data['date']:
        records = records.filter(date=filter_form.cleaned_data['date'])

    return render(
        request,
        'hr/attendance_list.html',
        {
            'records': records,
            'filter_form': filter_form,
            'can_manage': request.user.has_perm('hr.manage_attendance'),
        },
    )


@login_required
def attendance_create(request):
    _require_permission(request.user, 'hr.manage_attendance')
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    record = form.save(commit=False)
                    record.marked_by = request.user
                    record.save()
                    AuditLog.objects.create(
                        user=request.user,
                        action='recorded',
                        model_name='AttendanceRecord',
                        object_id=record.pk,
                        details=(
                            f'Attendance recorded for {record.employee.employee_number} '
                            f'on {record.date}: {record.status}.'
                        ),
                    )
            except IntegrityError:
                form.add_error(
                    None,
                    'An attendance record already exists for this employee and date.',
                )
            else:
                messages.success(request, 'Attendance recorded.')
                return redirect('hr:attendance')
    else:
        form = AttendanceForm()

    return render(request, 'hr/attendance_form.html', {'form': form, 'editing': False})


@login_required
def attendance_update(request, pk):
    _require_permission(request.user, 'hr.manage_attendance')
    record = get_object_or_404(
        AttendanceRecord.objects.select_related('employee'),
        pk=pk,
    )
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=record)
        if form.is_valid():
            previous = {
                'date': record.date,
                'status': record.status,
                'check_in': record.check_in,
                'check_out': record.check_out,
                'note': record.note,
            }
            try:
                with transaction.atomic():
                    record = form.save()
                    current = {
                        field: getattr(record, field)
                        for field in previous
                    }
                    changes = [
                        f'{field} changed'
                        for field, old_value in previous.items()
                        if old_value != current[field]
                    ]
                    AuditLog.objects.create(
                        user=request.user,
                        action='corrected',
                        model_name='AttendanceRecord',
                        object_id=record.pk,
                        details=(
                            f'Attendance corrected for {record.employee.employee_number}; '
                            f'{", ".join(changes) or "no field changes"}.'
                        ),
                    )
            except IntegrityError:
                form.add_error(
                    None,
                    'An attendance record already exists for this employee and date.',
                )
            else:
                messages.success(request, 'Attendance record corrected.')
                return redirect('hr:attendance')
    else:
        form = AttendanceForm(instance=record)

    return render(request, 'hr/attendance_form.html', {'form': form, 'editing': True})
