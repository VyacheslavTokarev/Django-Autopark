from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(url='dashboard/', permanent=True), name='index'),
    #Основные вкладки
    path('dashboard/', views.dashboard, name='dashboard'),
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('drivers/', views.driver_list, name='driver_list'),
    path('routes/', views.route_list, name='route_list'),
    path('refuels/', views.refuel_list, name='refuel_list'),
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('telemetry/', views.telemetry, name='telemetry'),
    path('telemetry/update_location/', views.update_vehicle_location, name='update_vehicle_location'),
    path('telemetry/update_status/', views.update_vehicle_status, name='update_vehicle_status'),

    #Формы
    path('vehicle_add/', views.vehicle_add, name='vehicle_add'),
    path('driver_add/', views.driver_add, name='driver_add'),
    path('route_add/', views.route_add, name='route_add'),
    path('refuel_add/', views.refuel_add, name='refuel_add'),
    path('maintenance_add/', views.maintenance_add, name='maintenance_add'),



]