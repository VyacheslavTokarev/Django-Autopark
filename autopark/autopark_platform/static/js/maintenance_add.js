// static/js/maintenance_add.js
const vehicleSelect = document.getElementById('vehicleSelect');
const mileageAtServiceSpan = document.getElementById('mileageAtService');
const mileageAtServiceHidden = document.getElementById('mileageAtServiceHidden');

function updateMileage() {
    const selectedOption = vehicleSelect.options[vehicleSelect.selectedIndex];
    if (selectedOption && selectedOption.value) {
        const currentMileage = parseFloat(selectedOption.dataset.currentMileage) || 0;
        mileageAtServiceSpan.value = currentMileage.toFixed(1);
        mileageAtServiceHidden.value = currentMileage;
    } else {
        mileageAtServiceSpan.value = '';
        mileageAtServiceHidden.value = '';
    }
}

vehicleSelect.addEventListener('change', updateMileage);
document.addEventListener('DOMContentLoaded', function() {
    if (vehicleSelect.value) {
        updateMileage();
    }
});