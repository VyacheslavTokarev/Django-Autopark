// static/js/telemetry.js
let map;
let currentRouteLayer = null;

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

async function drawRoute(startLat, startLng, endLat, endLng, isActive = false) {
    if (currentRouteLayer) {
        map.removeLayer(currentRouteLayer);
        currentRouteLayer = null;
    }
    const url = `https://router.project-osrm.org/route/v1/driving/${startLng},${startLat};${endLng},${endLat}?overview=full&geometries=geojson`;
    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.code === 'Ok' && data.routes.length > 0) {
            const geojson = data.routes[0].geometry;
            const routeStyle = {
                color: isActive ? '#ff5722' : '#2c7da0',  // активный – оранжевый, будущий – синий
                weight: 4,
                opacity: 0.8
            };
            currentRouteLayer = L.geoJSON(geojson, {
                style: routeStyle
            }).addTo(map);
            const bounds = L.latLngBounds([startLat, startLng], [endLat, endLng]);
            map.fitBounds(bounds, { padding: [30, 30] });
        } else {
            console.warn('Маршрут не найден');
        }
    } catch (error) {
        console.error('Ошибка запроса маршрута:', error);
    }
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

// Вспомогательная функция для получения CSRF-токена из куки
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
        const marker = L.marker([vehicle.latitude, vehicle.longitude], {
            icon: getIconByStatus(vehicle.status),
            draggable: true   // разрешаем перетаскивание
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

        if (vehicle.next_route && vehicle.next_route.departure_datetime) {
            const routeType = vehicle.next_route.is_active ? 'Текущий маршрут (в рейсе)' : 'Ближайший маршрут';
            const routeDate = new Date(vehicle.next_route.departure_datetime).toLocaleString();
            popupContent += `<br><hr><small>${routeType}: ${routeDate}</small>`;
        }

        marker.bindPopup(popupContent);

        marker.on('popupopen', async () => {
            if (vehicle.next_route && vehicle.next_route.departure_lat && vehicle.next_route.departure_lng &&
                vehicle.next_route.arrival_lat && vehicle.next_route.arrival_lng) {
                // Передаём флаг is_active, чтобы нарисовать маршрут другим цветом
                await drawRoute(
                    vehicle.next_route.departure_lat,
                    vehicle.next_route.departure_lng,
                    vehicle.next_route.arrival_lat,
                    vehicle.next_route.arrival_lng,
                    vehicle.next_route.is_active
                );
            } else {
                if (currentRouteLayer) map.removeLayer(currentRouteLayer);
                map.setView([vehicle.latitude, vehicle.longitude], 14);
            }
        });
    });
});