from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import AuditLog

from .forms import (
    PayrollLineFormSet,
    PayrollPaymentForm,
    PayrollReviewForm,
    PayrollRunForm,
)
from .models import PayrollRun
from .services import create_payroll_run


def _require_permission(user, permission):
    if not user.has_perm(permission):
        raise PermissionDenied


def _require_view_permission(user):
    if not any(
        user.has_perm(permission)
        for permission in (
            'payroll.view_payroll',
            'payroll.prepare_payroll',
            'payroll.approve_payroll',
            'payroll.record_payroll_payment',
        )
    ):
        raise PermissionDenied


def _can_edit_run(user, run):
    return user.has_perm('payroll.prepare_payroll') and (
        user.pk == run.prepared_by_id
        or user.has_perm('payroll.manage_all_payroll')
    )


@login_required
def payroll_list(request):
    _require_view_permission(request.user)
    return render(
        request,
        'payroll/payroll_list.html',
        {
            'runs': PayrollRun.objects.select_related(
                'prepared_by',
                'reviewed_by',
                'paid_by',
            ),
            'can_prepare': request.user.has_perm('payroll.prepare_payroll'),
        },
    )


@login_required
def payroll_create(request):
    _require_permission(request.user, 'payroll.prepare_payroll')
    if request.method == 'POST':
        form = PayrollRunForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    run = create_payroll_run(
                        year=form.cleaned_data['year'],
                        month=form.cleaned_data['month'],
                        currency_code=form.cleaned_data['currency_code'],
                        prepared_by=request.user,
                    )
                    AuditLog.objects.create(
                        user=request.user,
                        action='created',
                        model_name='PayrollRun',
                        object_id=run.pk,
                        details=f'Payroll run {run.period_label} created.',
                    )
            except ValidationError as error:
                form.add_error(None, error.messages[0])
            else:
                messages.success(request, 'Payroll draft created.')
                return redirect('payroll:detail', pk=run.pk)
    else:
        form = PayrollRunForm()

    return render(request, 'payroll/payroll_form.html', {'form': form})


@login_required
def payroll_detail(request, pk):
    _require_view_permission(request.user)
    run = get_object_or_404(
        PayrollRun.objects.select_related(
            'prepared_by',
            'approved_by',
            'reviewed_by',
            'paid_by',
        ).prefetch_related('lines__employee'),
        pk=pk,
    )
    can_edit = _can_edit_run(request.user, run) and run.status in (
        PayrollRun.Status.DRAFT,
        PayrollRun.Status.REJECTED,
    )
    return render(
        request,
        'payroll/payroll_detail.html',
        {
            'run': run,
            'lines': run.lines.all(),
            'can_edit': can_edit,
            'can_submit': can_edit,
            'can_review': request.user.has_perm('payroll.approve_payroll')
            and run.status == PayrollRun.Status.SUBMITTED
            and run.prepared_by_id != request.user.pk,
            'can_pay': request.user.has_perm('payroll.record_payroll_payment')
            and run.status == PayrollRun.Status.APPROVED,
        },
    )


@login_required
def payroll_update(request, pk):
    _require_permission(request.user, 'payroll.prepare_payroll')
    if request.method == 'POST':
        with transaction.atomic():
            run = get_object_or_404(
                PayrollRun.objects.select_for_update(),
                pk=pk,
            )
            if not _can_edit_run(request.user, run):
                raise PermissionDenied
            if run.status not in (
                PayrollRun.Status.DRAFT,
                PayrollRun.Status.REJECTED,
            ):
                raise PermissionDenied

            formset = PayrollLineFormSet(request.POST, instance=run)
            if formset.is_valid():
                changes = []
                for form in formset.forms:
                    if not form.has_changed():
                        continue
                    fields = form.cleaned_data
                    changed_amounts = []
                    for field_name in ('additions', 'deductions'):
                        if field_name in form.changed_data:
                            changed_amounts.append(
                                f'{field_name} {form.instance.employee.employee_number}: '
                                f'{getattr(form.instance, field_name)} to '
                                f'{fields[field_name]}'
                            )
                    if changed_amounts:
                        changes.extend(changed_amounts)
                    elif 'adjustment_note' in form.changed_data:
                        changes.append(
                            f'adjustment explanation updated for '
                            f'{form.instance.employee.employee_number}'
                        )

                formset.save()
                if changes:
                    AuditLog.objects.create(
                        user=request.user,
                        action='updated',
                        model_name='PayrollRun',
                        object_id=run.pk,
                        details=(
                            f'Payroll {run.period_label} changes: '
                            f'{"; ".join(changes)}.'
                        ),
                    )
                messages.success(request, 'Payroll adjustments saved.')
                return redirect('payroll:detail', pk=run.pk)
    else:
        run = get_object_or_404(PayrollRun, pk=pk)
        if not _can_edit_run(request.user, run):
            raise PermissionDenied
        if run.status not in (
            PayrollRun.Status.DRAFT,
            PayrollRun.Status.REJECTED,
        ):
            raise PermissionDenied
        formset = PayrollLineFormSet(instance=run)

    return render(
        request,
        'payroll/payroll_adjustments.html',
        {'run': run, 'formset': formset},
    )


@login_required
@require_POST
def payroll_submit(request, pk):
    _require_permission(request.user, 'payroll.prepare_payroll')
    with transaction.atomic():
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=pk)
        if not _can_edit_run(request.user, run):
            raise PermissionDenied
        try:
            run.submit()
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('payroll:detail', pk=run.pk)
        AuditLog.objects.create(
            user=request.user,
            action='submitted',
            model_name='PayrollRun',
            object_id=run.pk,
            details=f'Payroll run {run.period_label} submitted for approval.',
        )
    messages.success(request, 'Payroll submitted for approval.')
    return redirect('payroll:detail', pk=run.pk)


@login_required
@require_POST
def payroll_review(request, pk):
    _require_permission(request.user, 'payroll.approve_payroll')
    action = request.POST.get('action')
    form = PayrollReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'The review note is too long.')
        return redirect('payroll:detail', pk=pk)

    with transaction.atomic():
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=pk)
        try:
            if action == 'approve':
                run.approve(request.user)
                audit_action = 'approved'
            elif action == 'reject':
                run.reject(request.user, form.cleaned_data['review_note'])
                audit_action = 'returned'
            else:
                messages.error(request, 'Choose approve or return for changes.')
                return redirect('payroll:detail', pk=run.pk)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('payroll:detail', pk=run.pk)
        AuditLog.objects.create(
            user=request.user,
            action=audit_action,
            model_name='PayrollRun',
            object_id=run.pk,
            details=f'Payroll run {run.period_label} {audit_action}.',
        )

    messages.success(request, f'Payroll {audit_action}.')
    return redirect('payroll:detail', pk=run.pk)


@login_required
@require_POST
def payroll_record_payment(request, pk):
    _require_permission(request.user, 'payroll.record_payroll_payment')
    form = PayrollPaymentForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Enter a payment reference of 120 characters or fewer.')
        return redirect('payroll:detail', pk=pk)

    with transaction.atomic():
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=pk)
        try:
            with transaction.atomic():
                run.record_payment(
                    request.user,
                    form.cleaned_data['payment_reference'],
                )
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('payroll:detail', pk=run.pk)
        except IntegrityError:
            messages.error(
                request,
                'That payment reference has already been used; no payment was recorded.',
            )
            return redirect('payroll:detail', pk=run.pk)
        AuditLog.objects.create(
            user=request.user,
            action='paid',
            model_name='PayrollRun',
            object_id=run.pk,
            details=(
                f'Payroll run {run.period_label} marked paid; '
                f'reference {run.payment_reference}.'
            ),
        )

    messages.success(request, 'Payroll payment recorded.')
    return redirect('payroll:detail', pk=run.pk)
