// static/js/driver_add.js
document.addEventListener('DOMContentLoaded', function() {
    // Пример простого форматирования телефона (можно расширить по желанию)
    const phoneInput = document.querySelector('input[name="phone_number"]');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length > 11) value = value.slice(0, 11);
            if (value.startsWith('7') || value.startsWith('8')) {
                // примитивное форматирование
                if (value.length === 11 && value.startsWith('7')) {
                    e.target.value = value.replace(/(\d{1})(\d{3})(\d{3})(\d{2})(\d{2})/, '+$1 $2 $3-$4-$5');
                } else {
                    e.target.value = value;
                }
            } else {
                e.target.value = value;
            }
        });
    }
});