import json
import math

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.db.models import Q, F, DecimalField, Sum, Max, OuterRef, Subquery, FloatField, Value, CharField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib import messages
from .models import Vehicle, Driver, Route, FuelLog, Maintenance

from datetime import timedelta

def index(request):
    return render(request,'index.html')

def dashboard(request):
    now = timezone.now()
    today = now.date()
    week_later = today + timedelta(days=7)
    mileage_threshold = 1000  # км до следующего ТО

    # ---- Статистика по ТС ----
    total_vehicles = Vehicle.objects.count()
    free_vehicles = Vehicle.objects.filter(status=Vehicle.Status.FREE).count()
    maintenance_vehicles = Vehicle.objects.filter(status=Vehicle.Status.ON_MAINTENANCE).count()
    on_route_vehicles = Vehicle.objects.filter(status=Vehicle.Status.ON_ROUTE).count()

    # ---- Статистика по водителям ----
    total_drivers = Driver.objects.count()
    # Свободные водители – не назначены ни на один будущий/текущий маршрут (departure_datetime >= now - небольшая погрешность)
    # Проще: водители, у которых нет маршрутов с departure_datetime >= now и arrival_datetime is null
    busy_drivers_ids = Route.objects.filter(
        departure_datetime__gte=now,
        arrival_datetime__isnull=True,
        driver__isnull=False
    ).values_list('driver_id', flat=True).distinct()
    free_drivers = Driver.objects.exclude(id__in=busy_drivers_ids).count()

    # ---- Статистика по маршрутам ----
    total_routes = Route.objects.count()
    ongoing_routes = Route.objects.filter(
        departure_datetime__lte=now,
        arrival_datetime__isnull=True
    ).count()
    completed_routes = Route.objects.filter(arrival_datetime__isnull=False).count()

    # Самый длинный маршрут (по фактическому расстоянию, иначе по кратчайшему)
    longest_route = Route.objects.aggregate(
        max_dist=Coalesce(Max('actual_distance_km'), Max('shortest_distance_km'))
    )['max_dist']
    longest_route_distance = longest_route if longest_route is not None else None

    # ---- Ближайшие маршруты (до 5) ----
    upcoming_qs = Route.objects.filter(
        departure_datetime__gte=now,
        arrival_datetime__isnull=True
    ).select_related('driver__vehicle').order_by('departure_datetime')[:5]

    upcoming_routes = []
    for route in upcoming_qs:
        vehicle = route.driver.vehicle if route.driver else None
        fuel_level = vehicle.fuel_level if vehicle else None
        # Проверка необходимости ТО (по дате или пробегу)
        to_needed = False
        if vehicle:
            last_maintenance = vehicle.maintenances.order_by('-start_datetime').first()
            if last_maintenance:
                if last_maintenance.next_maintenance_date and last_maintenance.next_maintenance_date <= today:
                    to_needed = True
                if last_maintenance.next_maintenance_mileage and vehicle.current_mileage >= last_maintenance.next_maintenance_mileage:
                    to_needed = True
        upcoming_routes.append({
            'departure_datetime': route.departure_datetime,
            'vehicle_plate': vehicle.license_plate if vehicle else '—',
            'fuel_level': fuel_level,
            'to_needed': to_needed,
            'driver_name': route.driver.full_name if route.driver else 'Не назначен',
        })

    # ---- Статистика по заправкам ----
    fuel_logs = FuelLog.objects.all()
    total_fuel_cost = fuel_logs.aggregate(
        total=Sum(F('volume_liters') * F('price_per_liter'), output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total'] or 0
    total_fuel_logs = fuel_logs.count()
    last_fuel = fuel_logs.order_by('-datetime').first()
    last_fuel_price = last_fuel.price_per_liter if last_fuel else None

    # ТС с низким топливом (< 15 л)
    low_fuel_vehicles = Vehicle.objects.filter(fuel_level__lt=15, fuel_level__isnull=False)
    low_fuel_list = [
        {'brand': v.brand, 'model': v.model, 'license_plate': v.license_plate, 'fuel_level': v.fuel_level}
        for v in low_fuel_vehicles
    ]

    # ---- Статистика по ТО ----
    # Сумма затрат на ТО
    total_maintenance_cost = Maintenance.objects.aggregate(
        total=Sum('cost', output_field=DecimalField(max_digits=12, decimal_places=2))
    )['total'] or 0

    # ТС, которым скоро ТО (по дате или пробегу)
    # Определим queryset ТС, у которых есть запись ТО с заполненными next_maintenance_*
    vehicles_with_next_maintenance_date = Vehicle.objects.filter(
        Q(maintenances__next_maintenance_date__isnull=False)
    ).distinct()

    vehicles_with_next_maintenance_mileage = Vehicle.objects.filter(
        Q(maintenances__next_maintenance_mileage__isnull=False)
    ).distinct()

    # По дате (в пределах 7 дней)
    due_by_date_qs = vehicles_with_next_maintenance_date.filter(
        maintenances__next_maintenance_date__gte=today,
        maintenances__next_maintenance_date__lte=week_later
    ).distinct()
    maintenance_due_by_date = [
        {'vehicle_name': f"{v.brand} {v.model} ({v.license_plate})", 'next_maintenance_date': v.maintenances.order_by('-start_datetime').first().next_maintenance_date}
        for v in due_by_date_qs
    ]

    # По пробегу (осталось <= 1000 км)
    due_by_mileage_qs = vehicles_with_next_maintenance_mileage.filter(
        maintenances__next_maintenance_mileage__isnull=False,
        current_mileage__isnull=False
    ).annotate(
        mileage_left=F('maintenances__next_maintenance_mileage') - F('current_mileage')
    ).filter(mileage_left__lte=mileage_threshold, mileage_left__gte=0).distinct()
    maintenance_due_by_mileage = []
    for v in due_by_mileage_qs:
        last_m = v.maintenances.order_by('-next_maintenance_mileage').first()
        if last_m and last_m.next_maintenance_mileage:
            mileage_left = last_m.next_maintenance_mileage - (v.current_mileage or 0)
            maintenance_due_by_mileage.append({
                'vehicle_name': f"{v.brand} {v.model} ({v.license_plate})",
                'mileage_left': mileage_left
            })

    vehicles_with_next = vehicles_with_next_maintenance_date | vehicles_with_next_maintenance_mileage
    # Количество ТС, которым нужно ТО (прямо сейчас)
    needed_now = vehicles_with_next.filter(
        Q(maintenances__next_maintenance_date__lte=today) |
        Q(maintenances__next_maintenance_mileage__lte=F('current_mileage'))
    ).distinct().count()
    vehicles_due_maintenance_count = needed_now

    context = {
        'total_vehicles': total_vehicles,
        'free_vehicles': free_vehicles,
        'maintenance_vehicles': maintenance_vehicles,
        'on_route_vehicles': on_route_vehicles,
        'total_drivers': total_drivers,
        'free_drivers': free_drivers,
        'total_routes': total_routes,
        'ongoing_routes': ongoing_routes,
        'completed_routes': completed_routes,
        'longest_route_distance': longest_route_distance,
        'upcoming_routes': upcoming_routes,
        'total_fuel_cost': total_fuel_cost,
        'total_fuel_logs': total_fuel_logs,
        'last_fuel_price': last_fuel_price,
        'low_fuel_vehicles': low_fuel_list,
        'vehicles_due_maintenance_count': vehicles_due_maintenance_count,
        'total_maintenance_cost': total_maintenance_cost,
        'maintenance_due_by_date': maintenance_due_by_date,
        'maintenance_due_by_mileage': maintenance_due_by_mileage,
    }
    return render(request, 'index.html', context)

def vehicle_list(request):
    """
    View для отображения списка транспортных средств с поиском и фильтрацией по статусу.
    """
    # Получаем параметры из GET-запроса
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Начинаем с queryset всех активных? (лучше всех) Vehicle
    vehicles = Vehicle.objects.all()

    vehicles = vehicles.order_by('id')

    # Применяем поиск по марке, модели, госномеру, VIN
    if search_query:
        vehicles = vehicles.filter(
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(license_plate__icontains=search_query) |
            Q(vin__icontains=search_query)
        )

    # Применяем фильтр по статусу (если выбран не пустой и корректный)
    if status_filter in dict(Vehicle.Status.choices):
        vehicles = vehicles.filter(status=status_filter)

    context = {
        'vehicles': vehicles,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'vehicle_list.html', context)

def driver_list(request):
    """
    View для отображения списка водителей с поиском и фильтрацией по назначению ТС.
    """
    # Получаем параметры из GET-запроса
    search_query = request.GET.get('search', '').strip()
    assignment_filter = request.GET.get('assignment', '').strip()

    # Начинаем с queryset всех водителей
    drivers = Driver.objects.select_related('vehicle').all()

    # Применяем поиск по ФИО, удостоверению, телефону, email
    if search_query:
        drivers = drivers.filter(
            Q(full_name__icontains=search_query) |
            Q(license_number__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Применяем фильтр по назначению ТС
    if assignment_filter == 'assigned':
        drivers = drivers.filter(vehicle__isnull=False)
    elif assignment_filter == 'free':
        drivers = drivers.filter(vehicle__isnull=True)

    # Сортировка по id (или можно по ФИО, но не указано – оставим по id)
    drivers = drivers.order_by('id')

    context = {
        'drivers': drivers,
        'search_query': search_query,
        'assignment_filter': assignment_filter,
    }
    return render(request, 'driver_list.html', context)

def route_list(request):
    """
    View для отображения списка маршрутов с поиском, фильтрацией по статусу и сортировкой.
    """
    # Получаем параметры из GET-запроса
    search_query = request.GET.get('search', '').strip()
    route_status = request.GET.get('route_status', '').strip()
    sort_by = request.GET.get('sort_by', '').strip()

    # Текущее время
    now = timezone.now()

    # Базовый queryset с подгрузкой связанных данных (driver и vehicle)
    routes = Route.objects.select_related('driver__vehicle').all()

    # Поиск по адресам, имени водителя, госномеру ТС
    if search_query:
        routes = routes.filter(
            Q(departure_address__icontains=search_query) |
            Q(arrival_address__icontains=search_query) |
            Q(driver__full_name__icontains=search_query) |
            Q(driver__vehicle__license_plate__icontains=search_query)
        )

    # Фильтрация по статусу
    if route_status == 'upcoming':
        # Не начатые: departure_datetime > now И arrival_datetime отсутствует (или можно проверять, но по логике arrival ещё нет)
        routes = routes.filter(departure_datetime__gt=now, arrival_datetime__isnull=True)
    elif route_status == 'ongoing':
        # Выполняющиеся: departure_datetime <= now И arrival_datetime отсутствует
        routes = routes.filter(departure_datetime__lte=now, arrival_datetime__isnull=True)
    elif route_status == 'completed':
        # Завершённые: arrival_datetime не пусто
        routes = routes.filter(arrival_datetime__isnull=False)

    # Сортировка
    if sort_by == 'departure_asc':
        routes = routes.order_by('departure_datetime')
    elif sort_by == 'departure_desc':
        routes = routes.order_by('-departure_datetime')
    elif sort_by == 'distance_asc':
        routes = routes.order_by('shortest_distance_km')
    elif sort_by == 'distance_desc':
        routes = routes.order_by('-shortest_distance_km')
    else:
        # Сортировка по умолчанию, например, по убыванию даты отправления
        routes = routes.order_by('departure_datetime')

    context = {
        'routes': routes,
        'search_query': search_query,
        'route_status': route_status,
        'sort_by': sort_by,
        'now': now,
    }
    return render(request, 'route_list.html', context)

def refuel_list(request):
    """
    View для отображения списка заправок с поиском, фильтрацией по ТС и сортировкой по цене.
    """
    # Получаем параметры из GET-запроса
    search_query = request.GET.get('search', '').strip()
    vehicle_filter = request.GET.get('vehicle_id', '').strip()
    sort_by = request.GET.get('sort_by', '').strip()

    # Базовый queryset с аннотацией total_cost (volume_liters * price_per_liter)
    refuels = FuelLog.objects.select_related('vehicle').annotate(
        total_cost=Coalesce(F('volume_liters') * F('price_per_liter'), 0, output_field=DecimalField(max_digits=12, decimal_places=2))
    )

    # Поиск по госномеру, марке, модели ТС (можно также по дате, но по заданию не указано)
    if search_query:
        refuels = refuels.filter(
            Q(vehicle__license_plate__icontains=search_query) |
            Q(vehicle__brand__icontains=search_query) |
            Q(vehicle__model__icontains=search_query)
        )

    # Фильтрация по конкретному ТС
    if vehicle_filter and vehicle_filter.isdigit():
        refuels = refuels.filter(vehicle_id=int(vehicle_filter))

    # Сортировка по цене за литр
    if sort_by == 'price_asc':
        refuels = refuels.order_by('price_per_liter')
    elif sort_by == 'price_desc':
        refuels = refuels.order_by('-price_per_liter')
    else:
        # Сортировка по умолчанию: по дате заправки (новые сверху)
        refuels = refuels.order_by('-datetime')

    # Список всех ТС для фильтра
    vehicles_for_filter = Vehicle.objects.all().order_by('brand', 'model')

    context = {
        'refuels': refuels,
        'vehicles_for_filter': vehicles_for_filter,
        'search_query': search_query,
        'vehicle_filter': vehicle_filter,
        'sort_by': sort_by,
    }
    return render(request, 'refuel_list.html', context)

def maintenance_list(request):
    search_query = request.GET.get('search', '').strip()
    maintenance_filter = request.GET.get('maintenance_filter', 'all').strip()
    selected_vehicle_id = request.GET.get('vehicle_id', '').strip()

    maintenances = Maintenance.objects.select_related('vehicle').all()

    if search_query:
        maintenances = maintenances.filter(
            Q(description__icontains=search_query) |
            Q(vehicle__license_plate__icontains=search_query) |
            Q(vehicle__brand__icontains=search_query) |
            Q(vehicle__model__icontains=search_query)
        )

    now = timezone.now().date()
    today = now
    next_week = today + timedelta(days=7)
    mileage_threshold = 1000

    if maintenance_filter == 'ongoing':
        maintenances = maintenances.filter(end_datetime__isnull=True)
    elif maintenance_filter == 'needed_now':
        maintenances = maintenances.filter(
            Q(next_maintenance_date__lte=today) |
            Q(next_maintenance_mileage__isnull=False, vehicle__current_mileage__isnull=False,
              next_maintenance_mileage__lte=F('vehicle__current_mileage'))
        )
    elif maintenance_filter == 'due_by_date':
        maintenances = maintenances.filter(
            next_maintenance_date__gte=today,
            next_maintenance_date__lte=next_week
        )
    elif maintenance_filter == 'due_by_mileage':
        maintenances = maintenances.annotate(
            mileage_left=Coalesce(
                (F('next_maintenance_mileage') - F('vehicle__current_mileage')),
                Value(-1.0, output_field=FloatField())
            )
        ).filter(
            mileage_left__gte=0,
            mileage_left__lte=mileage_threshold
        )
    elif maintenance_filter == 'by_vehicle' and selected_vehicle_id:
        maintenances = maintenances.filter(vehicle_id=selected_vehicle_id)

    maintenances = maintenances.order_by('-start_datetime')

    vehicles_for_filter = Vehicle.objects.all().order_by('brand', 'model')

    context = {
        'maintenances': maintenances,
        'vehicles_for_filter': vehicles_for_filter,
        'search_query': search_query,
        'maintenance_filter': maintenance_filter,
        'selected_vehicle_id': selected_vehicle_id if selected_vehicle_id else '',
    }
    return render(request, 'maintenance_list.html', context)

def telemetry(request):
    now = timezone.now()

    # Подзапрос имени водителя
    driver_name_subquery = Driver.objects.filter(
        vehicle=OuterRef('pk')
    ).values('full_name')[:1]

    # Подзапрос активного маршрута (для ТС в рейсе)
    active_route_subquery = Route.objects.filter(
        driver__vehicle=OuterRef('pk'),
        departure_datetime__lte=now,
        arrival_datetime__isnull=True
    ).order_by('departure_datetime').values(
        'departure_latitude', 'departure_longitude',
        'arrival_latitude', 'arrival_longitude',
        'departure_datetime'
    )[:1]

    # Подзапрос ближайшего будущего маршрута (для свободных / на ТО)
    future_route_subquery = Route.objects.filter(
        driver__vehicle=OuterRef('pk'),
        departure_datetime__gte=now
    ).order_by('departure_datetime').values(
        'departure_latitude', 'departure_longitude',
        'arrival_latitude', 'arrival_longitude',
        'departure_datetime'
    )[:1]

    vehicles = Vehicle.objects.annotate(
        driver_name=Subquery(driver_name_subquery, output_field=CharField()),
        active_dep_lat=Subquery(active_route_subquery.values('departure_latitude')[:1], output_field=CharField()),
        active_dep_lng=Subquery(active_route_subquery.values('departure_longitude')[:1], output_field=CharField()),
        active_arr_lat=Subquery(active_route_subquery.values('arrival_latitude')[:1], output_field=CharField()),
        active_arr_lng=Subquery(active_route_subquery.values('arrival_longitude')[:1], output_field=CharField()),
        active_dep_datetime=Subquery(active_route_subquery.values('departure_datetime')[:1], output_field=CharField()),
        future_dep_lat=Subquery(future_route_subquery.values('departure_latitude')[:1], output_field=CharField()),
        future_dep_lng=Subquery(future_route_subquery.values('departure_longitude')[:1], output_field=CharField()),
        future_arr_lat=Subquery(future_route_subquery.values('arrival_latitude')[:1], output_field=CharField()),
        future_arr_lng=Subquery(future_route_subquery.values('arrival_longitude')[:1], output_field=CharField()),
        future_dep_datetime=Subquery(future_route_subquery.values('departure_datetime')[:1], output_field=CharField()),
    ).all()

    vehicles_data = []
    for v in vehicles:
        lat = v.latitude if v.latitude is not None else 45.0355
        lng = v.longitude if v.longitude is not None else 38.975

        # Для каждого ТС определяем, какой маршрут показывать
        if v.status == Vehicle.Status.ON_ROUTE and v.active_dep_lat:
            # Если ТС в рейсе и есть активный маршрут – показываем его
            route_info = {
                'departure_lat': float(v.active_dep_lat),
                'departure_lng': float(v.active_dep_lng),
                'arrival_lat': float(v.active_arr_lat),
                'arrival_lng': float(v.active_arr_lng),
                'departure_datetime': v.active_dep_datetime,
                'is_active': True
            }
        elif v.future_dep_lat:
            # Иначе показываем ближайший будущий маршрут (если есть)
            route_info = {
                'departure_lat': float(v.future_dep_lat),
                'departure_lng': float(v.future_dep_lng),
                'arrival_lat': float(v.future_arr_lat),
                'arrival_lng': float(v.future_arr_lng),
                'departure_datetime': v.future_dep_datetime,
                'is_active': False
            }
        else:
            route_info = None

        vehicles_data.append({
            'id': v.id,
            'brand': v.brand,
            'model': v.model,
            'license_plate': v.license_plate,
            'status': v.status,
            'status_display': v.get_status_display(),
            'current_mileage': v.current_mileage,
            'fuel_level': v.fuel_level,
            'latitude': lat,
            'longitude': lng,
            'driver_name': v.driver_name,
            'next_route': route_info,
        })

    vehicles_json = json.dumps(vehicles_data, ensure_ascii=False, default=str)
    return render(request, 'telemetry.html', {'vehicles_json': vehicles_json})

def haversine(lat1, lon1, lat2, lon2):
    """Расстояние между двумя точками в км (формула гаверсинуса)"""
    R = 6371  # радиус Земли в км
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@csrf_exempt
@require_POST
def update_vehicle_location(request):
    try:
        data = json.loads(request.body)
        vehicle_id = data.get('vehicle_id')
        new_lat = data.get('latitude')
        new_lng = data.get('longitude')

        if not all([vehicle_id, new_lat is not None, new_lng is not None]):
            return JsonResponse({'status': 'error', 'message': 'Missing fields'}, status=400)

        vehicle = Vehicle.objects.get(id=vehicle_id)
        old_lat = vehicle.latitude
        old_lng = vehicle.longitude

        # Определяем, какой маршрут сейчас актуален для этого ТС (аналогично telemetry)
        now = timezone.now()
        # Активный маршрут (в рейсе, не завершён)
        active_route = Route.objects.filter(
            driver__vehicle=vehicle,
            departure_datetime__lte=now,
            arrival_datetime__isnull=True
        ).order_by('departure_datetime').first()

        # Если нет активного – берём ближайший будущий
        if not active_route:
            active_route = Route.objects.filter(
                driver__vehicle=vehicle,
                departure_datetime__gte=now
            ).order_by('departure_datetime').first()

        # Обновляем координаты ТС
        vehicle.latitude = new_lat
        vehicle.longitude = new_lng
        vehicle.save(update_fields=['latitude', 'longitude'])

        # Если есть маршрут и это не будущий (или можно и для будущего, но логичнее для активного)
        if active_route:
            track = active_route.actual_track
            if track is None:
                track = []
            elif isinstance(track, str):
                track = json.loads(track)
            # Последняя точка трека
            last_point = track[-1] if track else None

            # Вычисляем пройденное расстояние от последней точки
            if last_point and 'lat' in last_point and 'lng' in last_point:
                dist = haversine(last_point['lat'], last_point['lng'], new_lat, new_lng)
                new_distance = last_point.get('distance_from_start', 0) + dist
            else:
                dist = 0
                new_distance = 0

            # Добавляем новую точку
            new_point = {
                'lat': new_lat,
                'lng': new_lng,
                'timestamp': timezone.now().isoformat(),
                'distance_from_start': round(new_distance, 3)
            }
            track.append(new_point)
            active_route.actual_track = track
            # Также обновляем фактическое пройденное расстояние в маршруте
            active_route.actual_distance_km = round(new_distance, 3)
            active_route.save(update_fields=['actual_track', 'actual_distance_km'])

        return JsonResponse({'status': 'ok'})
    except Vehicle.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Vehicle not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_POST
def update_vehicle_status(request):
    try:
        data = json.loads(request.body)
        vehicle_id = data.get('vehicle_id')
        new_status = data.get('status')
        if not vehicle_id or new_status not in dict(Vehicle.Status.choices):
            return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)
        vehicle = Vehicle.objects.get(id=vehicle_id)
        vehicle.status = new_status
        vehicle.save(update_fields=['status'])
        return JsonResponse({'status': 'ok'})
    except Vehicle.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Vehicle not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def vehicle_add(request):
    if request.method == 'POST':
        brand = request.POST.get('brand')
        model = request.POST.get('model')
        license_plate = request.POST.get('license_plate')
        status = request.POST.get('status')
        current_mileage = request.POST.get('current_mileage')
        year_of_manufacture = request.POST.get('year_of_manufacture')
        vin = request.POST.get('vin') or None
        fuel_level = request.POST.get('fuel_level') or None
        latitude = request.POST.get('latitude') or None
        longitude = request.POST.get('longitude') or None

        # Простейшая валидация
        if not all([brand, model, license_plate, status, current_mileage, year_of_manufacture]):
            messages.error(request, 'Заполните все обязательные поля')
            status_choices = Vehicle.Status.choices
            return render(request, 'vehicle_add.html', {'status_choices': status_choices})

        try:
            vehicle = Vehicle.objects.create(
                brand=brand,
                model=model,
                license_plate=license_plate,
                status=status,
                current_mileage=current_mileage,
                year_of_manufacture=year_of_manufacture,
                vin=vin,
                fuel_level=fuel_level,
                latitude=latitude,
                longitude=longitude
            )
            messages.success(request, f'ТС {vehicle.brand} {vehicle.model} успешно добавлено')
            return redirect('vehicle_list')
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении: {e}')

    # GET запрос
    status_choices = Vehicle.Status.choices
    context = {
        'status_choices': status_choices,
    }
    return render(request, 'vehicle_add.html', context)

def driver_add(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        license_number = request.POST.get('license_number')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        experience_years = request.POST.get('experience_years') or None
        vehicle_id = request.POST.get('vehicle_id')

        if not all([full_name, license_number, phone_number, email]):
            messages.error(request, 'Заполните все обязательные поля')
            # При ошибке передаём список свободных ТС
            free_vehicles = Vehicle.objects.filter(driver__isnull=True).order_by('brand', 'model')
            return render(request, 'driver_add.html', {'vehicles': free_vehicles})

        try:
            if Driver.objects.filter(license_number=license_number).exists():
                messages.error(request, 'Водитель с таким удостоверением уже существует')
                raise Exception('duplicate_license')
            if Driver.objects.filter(email=email).exists():
                messages.error(request, 'Водитель с таким email уже существует')
                raise Exception('duplicate_email')

            driver = Driver.objects.create(
                full_name=full_name,
                license_number=license_number,
                phone_number=phone_number,
                email=email,
                experience_years=experience_years,
                vehicle_id=vehicle_id if vehicle_id else None
            )
            messages.success(request, f'Водитель {driver.full_name} успешно добавлен')
            return redirect('driver_list')
        except Exception as e:
            if not str(e).startswith('duplicate'):
                messages.error(request, f'Ошибка при сохранении: {e}')
            free_vehicles = Vehicle.objects.filter(driver__isnull=True).order_by('brand', 'model')
            return render(request, 'driver_add.html', {'vehicles': free_vehicles})

    # GET запрос – только свободные ТС
    free_vehicles = Vehicle.objects.filter(driver__isnull=True).order_by('brand', 'model')
    context = {
        'vehicles': free_vehicles,
    }
    return render(request, 'driver_add.html', context)

def route_add(request):
    if request.method == 'POST':
        # Получаем данные из формы
        departure_lat = request.POST.get('departure_latitude')
        departure_lng = request.POST.get('departure_longitude')
        arrival_lat = request.POST.get('arrival_latitude')
        arrival_lng = request.POST.get('arrival_longitude')
        departure_address = request.POST.get('departure_address', '')
        arrival_address = request.POST.get('arrival_address', '')
        departure_datetime = request.POST.get('departure_datetime')
        shortest_distance = request.POST.get('shortest_distance_km')
        driver_id = request.POST.get('driver')
        vehicle_id = request.POST.get('vehicle_id')

        if not all([departure_lat, departure_lng, arrival_lat, arrival_lng, departure_datetime, driver_id]):
            # Ошибка валидации, можно вернуть форму с ошибкой
            pass  # Для простоты пропустим детальную обработку

        # Создаем маршрут
        route = Route.objects.create(
            departure_latitude=departure_lat,
            departure_longitude=departure_lng,
            arrival_latitude=arrival_lat,
            arrival_longitude=arrival_lng,
            departure_address=departure_address,
            arrival_address=arrival_address,
            departure_datetime=departure_datetime,
            shortest_distance_km=shortest_distance if shortest_distance else None,
            driver_id=driver_id,
            # vehicle_id не сохраняется напрямую в Route, он связан через водителя
        )
        return redirect('route_list')

    # GET запрос
    drivers = Driver.objects.select_related('vehicle').all().order_by('full_name')
    context = {
        'drivers': drivers,
        # Можно передать центр карты (например, координаты компании)
        'default_lat': 55.7558,
        'default_lng': 37.6173,
    }
    return render(request, 'route_add.html', context)

def refuel_add(request):
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle_id')
        datetime_str = request.POST.get('datetime')
        volume = request.POST.get('volume_liters')
        price = request.POST.get('price_per_liter')
        fuel_level_after = request.POST.get('fuel_level_after')
        mileage_at_refuel = request.POST.get('mileage_at_refuel')

        # Простейшая валидация
        if not all([vehicle_id, datetime_str, volume, price, fuel_level_after, mileage_at_refuel]):
            messages.error(request, 'Заполните все обязательные поля')
            # Повторно передаём список ТС
            vehicles = Vehicle.objects.all().order_by('brand', 'model')
            return render(request, 'refuel_add.html', {'vehicles': vehicles})

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            # Сохраняем заправку
            refuel = FuelLog.objects.create(
                vehicle=vehicle,
                datetime=datetime_str,
                volume_liters=volume,
                price_per_liter=price,
                fuel_level_after=fuel_level_after,
                mileage_at_refuel=mileage_at_refuel
            )
            # Обновляем уровень топлива в ТС
            vehicle.fuel_level = fuel_level_after
            vehicle.save(update_fields=['fuel_level'])

            messages.success(request, 'Заправка успешно добавлена')
            return redirect('refuel_list')
        except Vehicle.DoesNotExist:
            messages.error(request, 'Выбранное ТС не существует')
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении: {e}')

    # GET запрос
    vehicles = Vehicle.objects.all().order_by('brand', 'model')
    context = {
        'vehicles': vehicles,
    }
    return render(request, 'refuel_add.html', context)

def maintenance_add(request):
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle_id')
        start_datetime = request.POST.get('start_datetime')
        end_datetime = request.POST.get('end_datetime') or None
        description = request.POST.get('description') or None
        cost = request.POST.get('cost') or None
        mileage_at_service = request.POST.get('mileage_at_service')
        next_maintenance_date = request.POST.get('next_maintenance_date') or None
        next_maintenance_mileage = request.POST.get('next_maintenance_mileage') or None

        # Валидация
        if not all([vehicle_id, start_datetime, mileage_at_service]):
            messages.error(request, 'Заполните все обязательные поля (ТС, дата начала ТО)')
            vehicles = Vehicle.objects.all().order_by('brand', 'model')
            return render(request, 'maintenance_add.html', {'vehicles': vehicles})

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            maintenance = Maintenance.objects.create(
                vehicle=vehicle,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                description=description,
                cost=cost,
                mileage_at_service=mileage_at_service,
                next_maintenance_date=next_maintenance_date,
                next_maintenance_mileage=next_maintenance_mileage
            )
            # Если ТО завершено (есть end_datetime) и статус ТС был "На ТО" – можно вернуть статус "Свободен", но по заданию не требуется
            messages.success(request, 'Запись ТО успешно добавлена')
            return redirect('maintenance_list')
        except Vehicle.DoesNotExist:
            messages.error(request, 'Выбранное ТС не существует')
        except Exception as e:
            messages.error(request, f'Ошибка при сохранении: {e}')

    # GET запрос
    vehicles = Vehicle.objects.all().order_by('brand', 'model')
    context = {
        'vehicles': vehicles,
    }
    return render(request, 'maintenance_add.html', context)
