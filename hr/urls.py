from django.urls import path

from . import views

app_name = 'hr'

urlpatterns = [
    path('employees/', views.employee_list, name='employees'),
    path('employees/new/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/edit/', views.employee_update, name='employee_update'),
    path('attendance/', views.attendance_list, name='attendance'),
    path('attendance/new/', views.attendance_create, name='attendance_create'),
    path(
        'attendance/<int:pk>/edit/',
        views.attendance_update,
        name='attendance_update',
    ),
]
