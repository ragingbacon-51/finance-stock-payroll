from pathlib import Path

from django import forms

from .models import Expense


MAX_RECEIPT_SIZE = 5 * 1024 * 1024
RECEIPT_SIGNATURES = {
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.pdf': (b'%PDF-',),
}


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ('category', 'description', 'amount', 'occurred_on', 'receipt')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'occurred_on': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_receipt(self):
        receipt = self.cleaned_data.get('receipt')
        if not receipt:
            return receipt

        if receipt.size > MAX_RECEIPT_SIZE:
            raise forms.ValidationError('The receipt must be 5 MB or smaller.')

        extension = Path(receipt.name).suffix.lower()
        signatures = RECEIPT_SIGNATURES.get(extension)
        if not signatures:
            raise forms.ValidationError('Upload a JPG, PNG, or PDF receipt.')

        header = receipt.read(8)
        receipt.seek(0)
        if not any(header.startswith(signature) for signature in signatures):
            raise forms.ValidationError('The receipt content does not match its file type.')

        return receipt
