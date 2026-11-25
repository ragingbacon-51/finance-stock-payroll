from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expense_list, name='list'),
    path('new/', views.expense_create, name='create'),
    path('<int:pk>/', views.expense_detail, name='detail'),
    path('<int:pk>/receipt/', views.receipt_download, name='receipt'),
    path('<int:pk>/review/', views.expense_review, name='review'),
]
