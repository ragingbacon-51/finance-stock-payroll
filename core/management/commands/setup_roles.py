from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


ROLES = ('Admin', 'Accountant', 'Storekeeper', 'Manager')


class Command(BaseCommand):
    help = 'Create the standard project roles'

    def handle(self, *args, **options):
        review_permission = Permission.objects.get(
            content_type=ContentType.objects.get(
                app_label='expenses',
                model='expense',
            ),
            codename='review_expense',
        )
        view_stock_permission = Permission.objects.get(
            content_type=ContentType.objects.get(
                app_label='inventory',
                model='product',
            ),
            codename='view_stock',
        )
        manage_stock_permission = Permission.objects.get(
            content_type=ContentType.objects.get(
                app_label='inventory',
                model='stockmovement',
            ),
            codename='manage_stock',
        )
        employee_permissions = list(
            Permission.objects.filter(
                content_type=ContentType.objects.get(
                    app_label='hr',
                    model='employee',
                ),
                codename__in=[
                    'view_employee',
                    'manage_employees',
                    'view_attendance',
                    'manage_attendance',
                ],
            )
        )
        payroll_permissions = {
            permission.codename: permission
            for permission in Permission.objects.filter(
                content_type=ContentType.objects.get(
                    app_label='payroll',
                    model='payrollrun',
                ),
                codename__in=[
                    'view_payroll',
                    'prepare_payroll',
                    'manage_all_payroll',
                    'approve_payroll',
                    'record_payroll_payment',
                ],
            )
        }
        for name in ROLES:
            group, _ = Group.objects.get_or_create(name=name)
            if name in ('Admin', 'Accountant', 'Manager'):
                group.permissions.add(review_permission)
            group.permissions.add(view_stock_permission)
            if name in ('Admin', 'Storekeeper'):
                group.permissions.add(manage_stock_permission)
            if name in ('Admin', 'Accountant', 'Manager'):
                group.permissions.add(
                    *[
                        permission
                        for permission in employee_permissions
                        if permission.codename in (
                            'view_employee',
                            'view_attendance',
                        )
                    ]
                )
            if name in ('Admin', 'Manager'):
                group.permissions.add(
                    *[
                        permission
                        for permission in employee_permissions
                        if permission.codename in (
                            'manage_employees',
                            'manage_attendance',
                        )
                    ]
                )
            if name == 'Admin':
                group.permissions.add(*payroll_permissions.values())
            elif name == 'Accountant':
                group.permissions.add(
                    payroll_permissions['view_payroll'],
                    payroll_permissions['prepare_payroll'],
                    payroll_permissions['record_payroll_payment'],
                )
            elif name == 'Manager':
                group.permissions.add(
                    payroll_permissions['view_payroll'],
                    payroll_permissions['approve_payroll'],
                )

        self.stdout.write(self.style.SUCCESS('Roles ready'))
