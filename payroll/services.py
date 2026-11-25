from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from hr.models import Employee

from .models import PayrollLine, PayrollRun


@transaction.atomic
def create_payroll_run(*, year, month, currency_code, prepared_by):
    employees = list(
        Employee.objects.select_for_update().filter(
            is_active=True,
            salary_currency=currency_code,
        ).order_by('pk')
    )
    if not employees:
        raise ValidationError(
            'No active employees have a salary in this currency.'
        )

    try:
        run = PayrollRun.objects.create(
            year=year,
            month=month,
            currency_code=currency_code,
            prepared_by=prepared_by,
        )
    except IntegrityError as error:
        raise ValidationError(
            'A payroll run already exists for that month.'
        ) from error

    PayrollLine.objects.bulk_create(
        [
            PayrollLine(
                run=run,
                employee=employee,
                monthly_salary=employee.monthly_salary,
            )
            for employee in employees
        ]
    )
    return run
