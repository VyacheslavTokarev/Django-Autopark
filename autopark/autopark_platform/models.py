from django.db import models
from django.core.validators import MinValueValidator, RegexValidator


class Vehicle(models.Model):
    class Status(models.TextChoices):
        ON_ROUTE = 'on_route', 'В рейсе'
        ON_MAINTENANCE = 'on_maintenance', 'На ТО'
        FREE = 'free', 'Свободен'

    brand = models.CharField('Марка', max_length=100)
    model = models.CharField('Модель', max_length=100)
    license_plate = models.CharField('Госномер', max_length=20, unique=True)
    status = models.CharField('Статус активности', max_length=20, choices=Status.choices, default=Status.FREE)
    current_mileage = models.FloatField('Текущий пробег', validators=[MinValueValidator(0)])
    year_of_manufacture = models.PositiveSmallIntegerField('Год выпуска')

    vin = models.CharField('VIN-номер', max_length=17, blank=True, null=True, unique=True)
    fuel_level = models.FloatField('Уровень топлива в баке', blank=True, null=True, validators=[MinValueValidator(0)])
    latitude = models.FloatField('Широта', blank=True, null=True)
    longitude = models.FloatField('Долгота', blank=True, null=True)

    class Meta:
        verbose_name = 'Транспортное средство'
        verbose_name_plural = 'Транспортные средства'
        ordering = ['brand', 'model']

    def __str__(self):
        return f'{self.brand} {self.model} ({self.license_plate})'


class Driver(models.Model):
    full_name = models.CharField('ФИО', max_length=200)
    license_number = models.CharField('Водительское удостоверение', max_length=50, unique=True)
    phone_number = models.CharField('Номер телефона', max_length=20)
    email = models.EmailField('Электронная почта', unique=True)
    experience_years = models.PositiveSmallIntegerField('Стаж (лет)', blank=True, null=True)
    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver',
        verbose_name='Транспортное средство'
    )

    class Meta:
        verbose_name = 'Водитель'
        verbose_name_plural = 'Водители'
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class Route(models.Model):
    # Координаты отправления (обязательные)
    departure_latitude = models.FloatField('Широта отправления')
    departure_longitude = models.FloatField('Долгота отправления')
    # Координаты прибытия (обязательные)
    arrival_latitude = models.FloatField('Широта прибытия')
    arrival_longitude = models.FloatField('Долгота прибытия')

    departure_datetime = models.DateTimeField('Дата и время отправления')
    departure_address = models.CharField('Точка отправления (почтовый адрес)', max_length=255, blank=True, null=True)
    arrival_address = models.CharField('Точка прибытия (почтовый адрес)', max_length=255, blank=True, null=True)
    shortest_distance_km = models.FloatField('Расстояние кратчайшего пути (км)', blank=True, null=True,
                                             validators=[MinValueValidator(0)])
    actual_track = models.JSONField('Фактический трек', blank=True, null=True,
                                    help_text='Список координат с timestamp и пройденным расстоянием')
    arrival_datetime = models.DateTimeField('Дата и время прибытия', blank=True, null=True)
    actual_distance_km = models.FloatField('Фактически пройденное расстояние (км)', blank=True, null=True,
                                           validators=[MinValueValidator(0)])
    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='routes',
        verbose_name='Назначенный водитель'
    )

    class Meta:
        verbose_name = 'Маршрут'
        verbose_name_plural = 'Маршруты'
        ordering = ['-departure_datetime']

    def __str__(self):
        return f'Маршрут от {self.departure_datetime}'


class FuelLog(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='fuel_logs',
        verbose_name='Транспортное средство'
    )
    datetime = models.DateTimeField('Дата и время заправки')
    volume_liters = models.FloatField('Объем (л)', validators=[MinValueValidator(0)])
    price_per_liter = models.DecimalField('Цена за литр', max_digits=10, decimal_places=2,
                                          validators=[MinValueValidator(0)])
    fuel_level_after = models.FloatField('Объем топлива в баке после заправки (л)', validators=[MinValueValidator(0)])
    mileage_at_refuel = models.FloatField('Пробег ТС на момент заправки (км)', validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = 'Заправка'
        verbose_name_plural = 'Заправки'
        ordering = ['-datetime']

    def __str__(self):
        return f'Заправка {self.vehicle} от {self.datetime}'


class Maintenance(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenances',
        verbose_name='Транспортное средство'
    )
    start_datetime = models.DateTimeField('Дата и время начала ТО')
    end_datetime = models.DateTimeField('Дата и время окончания ТО', blank=True, null=True)
    description = models.TextField('Описание ТО', blank=True, null=True)
    cost = models.DecimalField('Стоимость ТО', max_digits=12, decimal_places=2, blank=True, null=True,
                               validators=[MinValueValidator(0)])
    mileage_at_service = models.FloatField('Пробег ТС на момент ТО (км)', blank=True, null=True,
                                           validators=[MinValueValidator(0)])
    next_maintenance_date = models.DateField('Дата следующего ТО', blank=True, null=True)
    next_maintenance_mileage = models.FloatField('Пробег для следующего ТО (км)', blank=True, null=True,
                                                 validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = 'Техническое обслуживание'
        verbose_name_plural = 'Техническое обслуживание'
        ordering = ['-start_datetime']

    def __str__(self):
        return f'ТО {self.vehicle} от {self.start_datetime}'


class Telemetry(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='telemetry',
        verbose_name='Транспортное средство'
    )
    latitude = models.FloatField('Широта')
    longitude = models.FloatField('Долгота')
    timestamp = models.DateTimeField('Дата и время получения данных')
    speed = models.FloatField('Скорость (км/ч)', blank=True, null=True, validators=[MinValueValidator(0)])
    fuel_level = models.FloatField('Уровень топлива в баке (л)', blank=True, null=True,
                                   validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = 'Телеметрия'
        verbose_name_plural = 'Телеметрия'
        ordering = ['-timestamp']

    def __str__(self):
        return f'Телеметрия {self.vehicle} в {self.timestamp}'