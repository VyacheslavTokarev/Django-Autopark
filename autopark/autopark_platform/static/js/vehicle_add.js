// static/js/vehicle_add.js
// Пока минимальная логика – можно добавить валидацию или подсказки по желанию.
document.addEventListener('DOMContentLoaded', function() {
    // Пример: автоформатирование госномера (буквы в верхний регистр)
    const licensePlateInput = document.querySelector('input[name="license_plate"]');
    if (licensePlateInput) {
        licensePlateInput.addEventListener('input', function(e) {
            e.target.value = e.target.value.toUpperCase();
        });
    }
});