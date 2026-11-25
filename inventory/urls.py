from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_list, name='list'),
    path('products/new/', views.product_create, name='product_create'),
    path('movements/new/', views.movement_create, name='movement_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
]
