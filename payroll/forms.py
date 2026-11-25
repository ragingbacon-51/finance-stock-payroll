from django import forms
from django.forms import inlineformset_factory

from core.forms import CurrencyCodeField

from .models import PayrollLine, PayrollRun


class PayrollRunForm(forms.ModelForm):
    currency_code = CurrencyCodeField(
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
        model = PayrollRun
        fields = ('year', 'month', 'currency_code')
        widgets = {
            'year': forms.NumberInput(attrs={'min': 2000, 'max': 9999}),
            'month': forms.NumberInput(attrs={'min': 1, 'max': 12}),
        }

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('year')
        month = cleaned_data.get('month')
        currency_code = cleaned_data.get('currency_code')
        if (
            year
            and month
            and currency_code
            and PayrollRun.objects.filter(
                year=year,
                month=month,
                currency_code=currency_code,
            ).exists()
        ):
            raise forms.ValidationError(
                'A payroll run already exists for that month and currency.'
            )
        return cleaned_data


class PayrollLineForm(forms.ModelForm):
    class Meta:
        model = PayrollLine
        fields = (
            'employee',
            'monthly_salary',
            'additions',
            'deductions',
            'adjustment_note',
        )
        widgets = {
            'additions': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'deductions': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'adjustment_note': forms.TextInput(attrs={'maxlength': 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].disabled = True
        self.fields['monthly_salary'].disabled = True


PayrollLineFormSet = inlineformset_factory(
    PayrollRun,
    PayrollLine,
    form=PayrollLineForm,
    extra=0,
    can_delete=False,
)


class PayrollReviewForm(forms.Form):
    review_note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 2}),
    )


class PayrollPaymentForm(forms.Form):
    payment_reference = forms.CharField(
        max_length=120,
        widget=forms.TextInput(
            attrs={'placeholder': 'Bank reference or payment voucher number'}
        ),
    )
