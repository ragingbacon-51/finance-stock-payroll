from django import forms

from .models import Product, StockMovement


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('sku', 'name', 'reorder_level')


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ('product', 'movement_type', 'quantity', 'reason')
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
