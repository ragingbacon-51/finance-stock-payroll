from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import AuditLog

from .forms import ExpenseForm
from .models import Expense


def _can_review(user):
    return user.has_perm('expenses.review_expense')


def _visible_expenses(user):
    expenses = Expense.objects.select_related('submitted_by', 'reviewed_by')
    if _can_review(user):
        return expenses
    return expenses.filter(submitted_by=user)


@login_required
def expense_list(request):
    return render(
        request,
        'expenses/expense_list.html',
        {
            'expenses': _visible_expenses(request.user),
            'can_review': _can_review(request.user),
        },
    )


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                expense = form.save(commit=False)
                expense.submitted_by = request.user
                expense.save()
                AuditLog.objects.create(
                    user=request.user,
                    action='submitted',
                    model_name='Expense',
                    object_id=expense.pk,
                    details=f'Expense {expense.pk} submitted for review.',
                )
            messages.success(request, 'Expense submitted for review.')
            return redirect('expenses:detail', pk=expense.pk)
    else:
        form = ExpenseForm()

    return render(request, 'expenses/expense_form.html', {'form': form})


@login_required
def expense_detail(request, pk):
    expense = get_object_or_404(_visible_expenses(request.user), pk=pk)
    return render(
        request,
        'expenses/expense_detail.html',
        {
            'expense': expense,
            'can_review': _can_review(request.user),
        },
    )


@login_required
def receipt_download(request, pk):
    expense = get_object_or_404(_visible_expenses(request.user), pk=pk)
    if not expense.receipt:
        raise Http404('No receipt was uploaded for this expense.')

    extension = Path(expense.receipt.name).suffix.lower()
    return FileResponse(
        expense.receipt.open('rb'),
        as_attachment=True,
        filename=f'expense-{expense.pk}{extension}',
        content_type='application/octet-stream',
    )


@login_required
@require_POST
def expense_review(request, pk):
    if not _can_review(request.user):
        raise PermissionDenied

    action = request.POST.get('action')
    note = request.POST.get('review_note', '')

    with transaction.atomic():
        expense = get_object_or_404(
            Expense.objects.select_for_update(),
            pk=pk,
        )
        try:
            if action == 'approve':
                expense.approve(request.user, note)
                audit_action = 'approved'
            elif action == 'reject':
                expense.reject(request.user, note)
                audit_action = 'rejected'
            else:
                messages.error(request, 'Choose approve or reject.')
                return redirect('expenses:detail', pk=expense.pk)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('expenses:detail', pk=expense.pk)

        AuditLog.objects.create(
            user=request.user,
            action=audit_action,
            model_name='Expense',
            object_id=expense.pk,
            details=f'Expense {expense.pk} {audit_action}.',
        )

    messages.success(request, f'Expense {audit_action}.')
    return redirect('expenses:detail', pk=expense.pk)
