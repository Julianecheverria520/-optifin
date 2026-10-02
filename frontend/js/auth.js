function cambiarTab(tab) {
    const fLogin = document.getElementById('form-login');
    const fRegistro = document.getElementById('form-registro');
    const tabLogin = document.getElementById('tab-login');
    const tabRegistro = document.getElementById('tab-registro');
    
    document.getElementById('error_msg').classList.add('hidden');

    if (tab === 'login') {
        fLogin.classList.remove('hidden');
        fRegistro.classList.add('hidden');
        tabLogin.className = 'flex-1 py-2 rounded-lg font-bold text-sm bg-white shadow text-gray-800 transition-all';
        tabRegistro.className = 'flex-1 py-2 rounded-lg font-bold text-sm text-gray-500 hover:text-gray-800 transition-all';
    } else {
        fLogin.classList.add('hidden');
        fRegistro.classList.remove('hidden');
        tabRegistro.className = 'flex-1 py-2 rounded-lg font-bold text-sm bg-white shadow text-gray-800 transition-all';
        tabLogin.className = 'flex-1 py-2 rounded-lg font-bold text-sm text-gray-500 hover:text-gray-800 transition-all';
    }
}

function mostrarError(msg) {
    const box = document.getElementById('error_msg');
    box.innerText = msg;
    box.classList.remove('hidden');
}

function iniciarSesionLocal(usuario, token, recordar) {
    const payload = JSON.stringify({ ...usuario, token });
    try {
        // Solo una sesión guardada a la vez
        localStorage.removeItem('optifin_user');
        sessionStorage.removeItem('optifin_user');
        (recordar ? localStorage : sessionStorage).setItem('optifin_user', payload);
    } catch (e) {
        return mostrarError("El navegador no permite guardar la sesión (¿navegación privada o cookies bloqueadas?).");
    }
    window.location.replace('dashboard.html');
}

// Evita doble envío mientras se espera la respuesta del servidor
async function enviando(form, accion) {
    const boton = form.querySelector('button[type="submit"]');
    const texto = boton.innerText;
    boton.disabled = true;
    boton.innerText = 'Un momento…';
    try {
        await accion();
    } finally {
        boton.disabled = false;
        boton.innerText = texto;
    }
}

document.getElementById('form-login').addEventListener('submit', async (e) => {
    e.preventDefault();
    document.getElementById('error_msg').classList.add('hidden');
    const recordar = document.getElementById('recordarme').checked;
    const body = {
        email: document.getElementById('log_email').value,
        password: document.getElementById('log_password').value,
        recordar
    };

    await enviando(e.target, async () => {
        try {
            const data = await api("/auth/login", { method: "POST", body });
            iniciarSesionLocal(data.usuario, data.token, recordar);
        } catch (err) {
            mostrarError(err.message);
        }
    });
});

document.getElementById('form-registro').addEventListener('submit', async (e) => {
    e.preventDefault();
    document.getElementById('error_msg').classList.add('hidden');
    const body = {
        nombre: document.getElementById('reg_nombre').value,
        email: document.getElementById('reg_email').value,
        password: document.getElementById('reg_password').value
    };
    if (body.password !== document.getElementById('reg_password2').value) {
        return mostrarError("Las contraseñas no coinciden.");
    }

    await enviando(e.target, async () => {
        try {
            const data = await api("/auth/registro", { method: "POST", body });
            if (data.requiere_confirmacion || !data.token) {
                // Supabase pide confirmar el correo antes de poder entrar
                document.getElementById('form-registro').reset();
                cambiarTab('login');
                document.getElementById('log_email').value = body.email;
                return mostrarError(data.mensaje || "Revisa tu correo para confirmar la cuenta y luego inicia sesión.");
            }
            iniciarSesionLocal(data.usuario, data.token, true);
        } catch (err) {
            mostrarError(err.message);
        }
    });
});