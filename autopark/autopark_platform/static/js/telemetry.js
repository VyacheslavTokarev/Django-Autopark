// static/js/telemetry.js
let map;
let routingControl = null;
let currentVehicleId = null;

const DEFAULT_CENTER = [45.0355, 38.975];
const DEFAULT_ZOOM = 12;

function initMap() {
    map = L.map('telemetryMap').setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CartoDB'
    }).addTo(map);
}

function getIconByStatus(status) {
    const icons = {
        'free': L.divIcon({
            className: 'custom-marker free',
            html: '<div style="background-color: #28a745; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
            iconSize: [18, 18],
            popupAnchor: [0, -9]
        }),
        'on_route': L.divIcon({
            className: 'custom-marker route',
            html: '<div style="background-color: #ffc107; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
            iconSize: [18, 18],
            popupAnchor: [0, -9]
        }),
        'on_maintenance': L.divIcon({
            className: 'custom-marker maintenance',
            html: '<div style="background-color: #dc3545; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>',
            iconSize: [18, 18],
            popupAnchor: [0, -9]
        })
    };
    return icons[status] || icons['free'];
}

function drawRoute(startLat, startLng, endLat, endLng, isActive = false) {
    console.log('drawRoute вызван', startLat, startLng, endLat, endLng, isActive);

    // Удаляем предыдущий маршрут
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }

    // Показываем контейнер
    const container = document.getElementById('routingContainer');
    if (container) container.style.display = 'block';

    // Создаём панель маршрута
    routingControl = L.Routing.control({
        waypoints: [
            L.latLng(startLat, startLng),
            L.latLng(endLat, endLng)
        ],
        routeWhileDragging: false,
        show: true,
        collapsible: true,
        fitSelectedRoutes: false,
        lineOptions: {
            styles: [{ color: isActive ? '#ff5722' : '#2c7da0', weight: 4, opacity: 0.8 }]
        }
    }).addTo(map);

    // Дополнительно: принудительно показываем контейнер, если плагин его не создал
    setTimeout(() => {
        const dynamicContainer = document.querySelector('.leaflet-routing-container');
        if (dynamicContainer && container !== dynamicContainer) {
            dynamicContainer.style.display = 'block';
        }
    }, 100);
}

function sendNewCoordinates(vehicleId, lat, lng) {
    fetch('/telemetry/update_location/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            vehicle_id: vehicleId,
            latitude: lat,
            longitude: lng
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            console.log(`Координаты ТС ${vehicleId} обновлены`);
        } else {
            console.error('Ошибка обновления:', data.message);
        }
    })
    .catch(error => console.error('AJAX error:', error));
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', () => {
    initMap();

    if (!vehiclesData || vehiclesData.length === 0) {
        console.warn('Нет данных о транспортных средствах');
        return;
    }

    vehiclesData.forEach(vehicle => {
        // Проверка, есть ли координаты
        if (!vehicle.latitude || !vehicle.longitude) {
            console.warn(`ТС ${vehicle.id} не имеет координат`);
            return;
        }

        const marker = L.marker([vehicle.latitude, vehicle.longitude], {
            icon: getIconByStatus(vehicle.status),
            draggable: true
        }).addTo(map);

        marker.on('dragend', function(event) {
            const newPos = event.target.getLatLng();
            sendNewCoordinates(vehicle.id, newPos.lat, newPos.lng);
        });

        let popupContent = `
            <strong>${vehicle.brand} ${vehicle.model}</strong><br>
            Госномер: ${vehicle.license_plate}<br>
            Статус: ${vehicle.status_display}<br>
            Пробег: ${vehicle.current_mileage} км<br>
            Топливо: ${vehicle.fuel_level !== null ? vehicle.fuel_level + ' л' : '—'}<br>
            ${vehicle.driver_name ? `Водитель: ${vehicle.driver_name}` : ''}
        `;

        if (vehicle.next_route && vehicle.next_route.departure_lat) {
            const routeType = vehicle.next_route.is_active ? 'Текущий маршрут (в рейсе)' : 'Ближайший маршрут';
            const routeDate = new Date(vehicle.next_route.departure_datetime).toLocaleString();
            popupContent += `<br><hr><small>${routeType}: ${routeDate}</small>`;
        }

        marker.bindPopup(popupContent);

        marker.on('popupopen', () => {
            console.log('popupopen для ТС', vehicle.id, vehicle.next_route);
            if (vehicle.next_route && vehicle.next_route.departure_lat && vehicle.next_route.departure_lng &&
                vehicle.next_route.arrival_lat && vehicle.next_route.arrival_lng) {
                drawRoute(
                    vehicle.next_route.departure_lat,
                    vehicle.next_route.departure_lng,
                    vehicle.next_route.arrival_lat,
                    vehicle.next_route.arrival_lng,
                    vehicle.next_route.is_active || false
                );
            } else {
                console.warn('Нет route_info для ТС, панель не появится');
                // Если маршрута нет – скрываем контейнер
                const container = document.getElementById('routingContainer');
                if (container) container.style.display = 'none';
                if (routingControl) {
                    map.removeControl(routingControl);
                    routingControl = null;
                }
                map.setView([vehicle.latitude, vehicle.longitude], 14);
            }
        });
    });
});