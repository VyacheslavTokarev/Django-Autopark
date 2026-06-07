// static/js/refuel.js
const vehicleSelect = document.getElementById('vehicleSelect');
const volumeInput = document.getElementById('volume');
const currentMileageInput = document.getElementById('currentMileage');
const mileageAtRefuelHidden = document.getElementById('mileageAtRefuel');
const currentFuelLevelInput = document.getElementById('currentFuelLevel');
const fuelLevelAfterInput = document.getElementById('fuelLevelAfter');
const fuelLevelAfterHidden = document.getElementById('fuelLevelAfterHidden');

function updateVehicleData() {
    const selectedOption = vehicleSelect.options[vehicleSelect.selectedIndex];
    if (selectedOption && selectedOption.value) {
        const fuelLevel = parseFloat(selectedOption.dataset.fuelLevel) || 0;
        const mileage = parseFloat(selectedOption.dataset.currentMileage) || 0;
        currentFuelLevelInput.value = fuelLevel.toFixed(2);
        currentMileageInput.value = mileage.toFixed(1);
        mileageAtRefuelHidden.value = mileage;
        updateFuelAfter();
    } else {
        currentFuelLevelInput.value = '';
        currentMileageInput.value = '';
        mileageAtRefuelHidden.value = '';
        fuelLevelAfterInput.value = '';
        fuelLevelAfterHidden.value = '';
    }
}

function updateFuelAfter() {
    const selectedOption = vehicleSelect.options[vehicleSelect.selectedIndex];
    if (selectedOption && selectedOption.value) {
        const currentFuel = parseFloat(selectedOption.dataset.fuelLevel) || 0;
        const volume = parseFloat(volumeInput.value) || 0;
        const after = currentFuel + volume;
        fuelLevelAfterInput.value = after.toFixed(2);
        fuelLevelAfterHidden.value = after;
    }
}

vehicleSelect.addEventListener('change', updateVehicleData);
volumeInput.addEventListener('input', updateFuelAfter);
// инициализация при загрузке, если ТС уже выбрано (например, при ошибке валидации)
document.addEventListener('DOMContentLoaded', function() {
    if (vehicleSelect.value) {
        updateVehicleData();
    }
});