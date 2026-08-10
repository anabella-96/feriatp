// =============================================================================
//  SISTEMA DE CONTROL DE ASISTENCIA BIOMÉTRICA (Asistec)
//  ARCHIVO: front/js/auth.js
//
//  PROPÓSITO:
//    Lógica mínima para las páginas de autenticación (login.html y registro.html).
//    Valida en el cliente que las contraseñas coincidan (en el registro) antes
//    de enviar el formulario; el resto de la validación la hace el servidor.
//
//  SOLO SE CARGA EN ESAS DOS PÁGINAS (no está en el dashboard).
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {

    // --- Registro: verificar que ambas contraseñas coincidan ---
    const formRegistro = document.querySelector('form[action="/registro"]');
    if (formRegistro) {
        formRegistro.addEventListener('submit', function (e) {
            const password = document.getElementById('password');
            const password2 = document.getElementById('password2');

            // Los inputs deben existir en el formulario de registro.
            if (!password || !password2) return;

            if (password.value !== password2.value) {
                e.preventDefault(); // Evitar enviar el formulario.
                password2.setCustomValidity('las contraseñas no coinciden');
                password2.reportValidity(); // Mostrar el mensaje del navegador.
            } else {
                password2.setCustomValidity(''); // Limpiar la validación previa.
            }
        });

        // Al escribir de nuevo, limpiar el estado "inválido" del input.
        const p2 = document.getElementById('password2');
        if (p2) {
            p2.addEventListener('input', function () { this.setCustomValidity(''); });
        }
    }
});