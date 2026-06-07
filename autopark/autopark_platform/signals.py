from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Vehicle, Route, Maintenance

def update_vehicle_status(vehicle):
    """Обновляет статус ТС на основе активных ТО и маршрутов"""
    if not vehicle:
        return

    # Проверяем незавершённое ТО
    if Maintenance.objects.filter(vehicle=vehicle, end_datetime__isnull=True).exists():
        new_status = Vehicle.Status.ON_MAINTENANCE
    # Проверяем активный маршрут
    elif Route.objects.filter(
        driver__vehicle=vehicle,
        departure_datetime__lte=timezone.now(),
        arrival_datetime__isnull=True
    ).exists():
        new_status = Vehicle.Status.ON_ROUTE
    else:
        new_status = Vehicle.Status.FREE

    if vehicle.status != new_status:
        vehicle.status = new_status
        vehicle.save(update_fields=['status'])


@receiver(post_save, sender=Maintenance)
@receiver(post_delete, sender=Maintenance)
def maintenance_changed(sender, instance, **kwargs):
    """При изменении или удалении ТО обновляем статус ТС"""
    update_vehicle_status(instance.vehicle)


@receiver(post_save, sender=Route)
@receiver(post_delete, sender=Route)
def route_changed(sender, instance, **kwargs):
    """При изменении или удалении маршрута обновляем статус ТС (через водителя)"""
    if instance.driver and instance.driver.vehicle:
        update_vehicle_status(instance.driver.vehicle)