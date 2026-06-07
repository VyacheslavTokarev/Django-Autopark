// static/js/route_add.js
let map;
let markerStart = null;
let markerEnd = null;
let routingControl = null;

const startLatInput = document.getElementById('departure_latitude');
const startLngInput = document.getElementById('departure_longitude');
const endLatInput = document.getElementById('arrival_latitude');
const endLngInput = document.getElementById('arrival_longitude');
const startAddrInput = document.getElementById('departure_address');
const endAddrInput = document.getElementById('arrival_address');
const distanceInput = document.getElementById('shortest_distance_km');
const driverSelect = document.getElementById('driver');
const vehicleDisplay = document.getElementById('vehicle_display');
const vehicleIdHidden = document.getElementById('vehicle_id');

// Центр карты по умолчанию (например, Москва)
const defaultCenter = [55.7558, 37.6173];

function initMap() {
    map = L.map('map').setView(defaultCenter, 10);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CartoDB'
    }).addTo(map);

    // Геокодер (поиск адреса)
    const geocoder = L.Control.geocoder({
        defaultMarkGeocode: false,
        position: 'topleft',
        placeholder: 'Поиск адреса...'
    }).on('markgeocode', function(e) {
        const center = e.geocode.center;
        // Определяем, какая точка сейчас редактируется (по фокусу или последнему клику)
        // По умолчанию - отправление, если точка прибытия не задана
        if (!markerEnd || (markerStart && !markerEnd)) {
            setStartPoint(center.lat, center.lng);
        } else {
            setEndPoint(center.lat, center.lng);
        }
    }).addTo(map);

    // Клик на карте
    map.on('click', function(e) {
        if (!markerStart) {
            setStartPoint(e.latlng.lat, e.latlng.lng);
        } else {
            setEndPoint(e.latlng.lat, e.latlng.lng);
        }
    });
}

function setStartPoint(lat, lng) {
    if (markerStart) map.removeLayer(markerStart);
    markerStart = L.marker([lat, lng], { draggable: true }).addTo(map);
    markerStart.on('dragend', function() {
        const pos = markerStart.getLatLng();
        updateStartFields(pos.lat, pos.lng);
        reverseGeocode(pos.lat, pos.lng, startAddrInput);
        if (markerEnd) calcRoute();
    });
    updateStartFields(lat, lng);
    reverseGeocode(lat, lng, startAddrInput);
    if (markerEnd) calcRoute();
}

function setEndPoint(lat, lng) {
    if (markerEnd) map.removeLayer(markerEnd);
    markerEnd = L.marker([lat, lng], { draggable: true }).addTo(map);
    markerEnd.on('dragend', function() {
        const pos = markerEnd.getLatLng();
        updateEndFields(pos.lat, pos.lng);
        reverseGeocode(pos.lat, pos.lng, endAddrInput);
        calcRoute();
    });
    updateEndFields(lat, lng);
    reverseGeocode(lat, lng, endAddrInput);
    calcRoute();
}

function updateStartFields(lat, lng) {
    startLatInput.value = lat;
    startLngInput.value = lng;
}

function updateEndFields(lat, lng) {
    endLatInput.value = lat;
    endLngInput.value = lng;
}

function reverseGeocode(lat, lng, targetInput) {
    fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`)
        .then(res => res.json())
        .then(data => {
            if (data.display_name) targetInput.value = data.display_name;
            else targetInput.value = '';
        })
        .catch(() => targetInput.value = '');
}

function calcRoute() {
    const startLat = parseFloat(startLatInput.value);
    const startLng = parseFloat(startLngInput.value);
    const endLat = parseFloat(endLatInput.value);
    const endLng = parseFloat(endLngInput.value);
    if (isNaN(startLat) || isNaN(startLng) || isNaN(endLat) || isNaN(endLng)) return;

    if (routingControl) map.removeControl(routingControl);
    routingControl = L.Routing.control({
        waypoints: [
            L.latLng(startLat, startLng),
            L.latLng(endLat, endLng)
        ],
        routeWhileDragging: false,
        show: false,
        lineOptions: { styles: [{ color: '#2c7da0', weight: 4 }] }
    }).on('routesfound', function(e) {
        const route = e.routes[0];
        const distanceKm = route.summary.totalDistance / 1000;
        distanceInput.value = distanceKm.toFixed(3);
    }).addTo(map);
}

// При смене водителя подставляем ТС
driverSelect.addEventListener('change', function() {
    const selected = driverSelect.options[driverSelect.selectedIndex];
    const vehicleId = selected.getAttribute('data-vehicle-id');
    const vehiclePlate = selected.getAttribute('data-vehicle-plate');
    if (vehicleId) {
        vehicleDisplay.value = vehiclePlate;
        vehicleIdHidden.value = vehicleId;
    } else {
        vehicleDisplay.value = 'Нет назначенного ТС';
        vehicleIdHidden.value = '';
    }
});

// Инициализация карты после загрузки страницы
document.addEventListener('DOMContentLoaded', initMap);