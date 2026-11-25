from django.urls import path

from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.payroll_list, name='list'),
    path('new/', views.payroll_create, name='create'),
    path('<int:pk>/', views.payroll_detail, name='detail'),
    path('<int:pk>/adjustments/', views.payroll_update, name='update'),
    path('<int:pk>/submit/', views.payroll_submit, name='submit'),
    path('<int:pk>/review/', views.payroll_review, name='review'),
    path('<int:pk>/payment/', views.payroll_record_payment, name='payment'),
]
