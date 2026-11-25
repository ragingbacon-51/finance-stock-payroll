from django import forms
from django.core.validators import RegexValidator


class CurrencyCodeField(forms.CharField):
    default_validators = [
        RegexValidator(
            regex=r'^[A-Z]{3}$',
            message='Enter a 3-letter currency code.',
        )
    ]

    def to_python(self, value):
        value = super().to_python(value)
        return value.upper() if value else value
