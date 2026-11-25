from django import forms

from core.forms import CurrencyCodeField

from .models import AttendanceRecord, Employee


class EmployeeForm(forms.ModelForm):
    salary_currency = CurrencyCodeField(
        max_length=3,
        min_length=3,
        widget=forms.TextInput(
            attrs={
                'maxlength': 3,
                'minlength': 3,
                'placeholder': 'KES',
                'style': 'text-transform: uppercase',
            }
        ),
        help_text='Use a 3-letter ISO 4217 currency code.',
    )

    class Meta:
        model = Employee
        fields = (
            'employee_number',
            'first_name',
            'last_name',
            'email',
            'phone',
            'job_title',
            'start_date',
            'monthly_salary',
            'salary_currency',
            'user',
            'is_active',
        )
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'monthly_salary': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = (
            'employee',
            'date',
            'status',
            'check_in',
            'check_out',
            'note',
        )
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in': forms.TimeInput(attrs={'type': 'time'}),
            'check_out': forms.TimeInput(attrs={'type': 'time'}),
            'note': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')

        if bool(check_in) != bool(check_out):
            raise forms.ValidationError(
                'Enter both clock-in and clock-out times, or leave both blank.'
            )
        if status != AttendanceRecord.Status.PRESENT and (check_in or check_out):
            raise forms.ValidationError(
                'Clock-in and clock-out times can only be recorded for present staff.'
            )
        if check_in and check_out and check_out <= check_in:
            raise forms.ValidationError(
                'Clock-out must be later than clock-in on the same day.'
            )
        return cleaned_data


class AttendanceFilterForm(forms.Form):
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
