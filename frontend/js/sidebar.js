// Menú lateral compartido por todas las páginas protegidas.
// En pantallas grandes es una columna fija; en celulares se oculta y se abre con el botón ☰
// de la barra superior, como un cajón sobre el contenido.

const ENLACES_MENU = [
    { pagina: 'dashboard', href: 'dashboard.html', texto: 'Resumen', icono: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { pagina: 'transacciones', href: 'index.html', texto: 'Movimientos', icono: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
    { pagina: 'planificacion', href: 'planificacion.html', texto: 'Presupuesto', icono: 'M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z' },
    { pagina: 'deudas', href: 'deudas.html', texto: 'Deudas', icono: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z' },
    { separador: true },
    { pagina: 'configuracion', href: 'configuracion.html', texto: 'Cuentas', icono: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
    { pagina: 'categorias', href: 'categorias.html', texto: 'Categorías', icono: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z' },
];

const icono = (d, clase = 'w-5 h-5') =>
    `<svg class="${clase}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${d}"></path></svg>`;

const LOGO = '<svg class="w-8 h-8 text-blue-400" fill="currentColor" viewBox="0 0 24 24"><path d="M3 13h2v8H3zm4-5h2v13H7zm4 4h2v9h-2zm4-6h2v15h-2zm4-4h2v19h-2z"/></svg>';

// Ajustes para celulares que aplican a todas las páginas
const ESTILOS_MOVIL = `
    @media (max-width: 767px) {
        /* Espacio para la barra superior y márgenes más pequeños. min-width: 0 evita que el
           contenido más ancho (tablas, selectores) estire la página más allá de la pantalla */
        body > main { padding: 4.5rem 1rem 1.5rem !important; min-width: 0; width: 100%; }
        body > main > *, body > main .grid > * { min-width: 0; }
        body > main .p-8 { padding: 1rem !important; }
        body > main .p-6 { padding: 1rem !important; }
        body > main header.sticky { position: static; padding: 0 0 1rem !important; }
        body > main h2.text-3xl { font-size: 1.5rem; line-height: 2rem; }
        /* Evita que iOS haga zoom al tocar un campo */
        input, select, textarea { font-size: 16px !important; }
        /* Las tablas se desplazan de lado dentro de su tarjeta, no toda la página */
        table th, table td { white-space: nowrap; }
    }
    body.menu-abierto { overflow: hidden; }
`;

function cargarSidebar(paginaActiva) {
    // Sin sesión, config.js ya está redirigiendo al login
    if (!USUARIO_ACTUAL) return;

    const nombre = USUARIO_ACTUAL.nombre || USUARIO_ACTUAL.email || 'Usuario';
    const enlaces = ENLACES_MENU.map(e => e.separador
        ? '<div class="mt-6 mb-3 px-4"><hr class="border-[#1a295c]"></div>'
        : `<a href="${e.href}" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === e.pagina ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
               ${icono(e.icono)}<span class="text-sm font-medium">${e.texto}</span>
           </a>`).join('');

    const contenedor = document.getElementById('sidebar-container');
    // En celular: cajón fijo fuera de pantalla; desde md (768px): columna normal
    contenedor.className = 'fixed inset-y-0 left-0 z-40 w-64 h-full -translate-x-full transition-transform duration-200 md:static md:translate-x-0 md:z-auto shrink-0';
    contenedor.innerHTML = `
        <div class="flex flex-col h-full bg-[#111c43] text-white w-64 shadow-xl font-sans overflow-y-auto">
            <div class="p-6 pt-8 pb-6 flex items-start justify-between">
                <div>
                    <div class="flex items-center gap-3 mb-1">${LOGO}<h1 class="text-2xl font-bold tracking-wide">OptiFin</h1></div>
                    <p class="text-gray-400 text-xs ml-11">Tu dinero, en orden</p>
                </div>
                <button type="button" onclick="alternarMenu(false)" class="md:hidden text-gray-400 hover:text-white text-2xl leading-none" aria-label="Cerrar menú">×</button>
            </div>
            <nav class="flex-1 px-4 space-y-1">${enlaces}</nav>
            <div class="p-4 mb-2">
                <div class="flex items-center gap-3 p-3 rounded-xl bg-[#0d1636]">
                    <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold text-white shadow shrink-0">${esc(nombre.charAt(0).toUpperCase())}</div>
                    <p class="flex-1 min-w-0 text-sm font-medium text-white truncate">${esc(nombre)}</p>
                    <button type="button" onclick="abrirCambioPassword()" class="text-gray-400 hover:text-blue-300 transition-colors" title="Cambiar contraseña" aria-label="Cambiar contraseña">
                        ${icono('M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z')}
                    </button>
                    <button type="button" onclick="cerrarSesion()" class="text-gray-400 hover:text-red-400 transition-colors" title="Cerrar sesión" aria-label="Cerrar sesión">
                        ${icono('M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1')}
                    </button>
                </div>
            </div>
        </div>`;

    // Barra superior (solo celular), fondo oscuro del cajón y estilos móviles: una sola vez por página
    if (!document.getElementById('barra-movil')) {
        const titulo = (ENLACES_MENU.find(e => e.pagina === paginaActiva) || {}).texto || 'OptiFin';
        document.body.insertAdjacentHTML('afterbegin', `
            <div id="barra-movil" class="md:hidden fixed top-0 inset-x-0 z-30 h-14 bg-[#111c43] text-white flex items-center gap-3 px-4 shadow">
                <button type="button" onclick="alternarMenu(true)" class="p-1 -ml-1" aria-label="Abrir menú">
                    ${icono('M4 6h16M4 12h16M4 18h16', 'w-6 h-6')}
                </button>
                <span class="font-bold tracking-wide">OptiFin</span>
                <span class="text-gray-400 text-sm truncate">· ${esc(titulo)}</span>
            </div>
            <div id="fondo-menu" onclick="alternarMenu(false)" class="hidden md:hidden fixed inset-0 z-30 bg-black/50"></div>`);
        const estilos = document.createElement('style');
        estilos.textContent = ESTILOS_MOVIL;
        document.head.appendChild(estilos);
    }
}

window.alternarMenu = function(abrir) {
    document.getElementById('sidebar-container').classList.toggle('-translate-x-full', !abrir);
    document.getElementById('fondo-menu').classList.toggle('hidden', !abrir);
    document.body.classList.toggle('menu-abierto', abrir);
};

// Cerrar el cajón con Escape
document.addEventListener('keydown', e => { if (e.key === 'Escape' && document.getElementById('fondo-menu')) alternarMenu(false); });

// ---------- Cambiar contraseña ----------

window.abrirCambioPassword = function() {
    alternarMenu(false);
    if (document.getElementById('modal-password')) return;
    document.body.insertAdjacentHTML('beforeend', `
        <div id="modal-password" class="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4">
            <form id="form-password" class="bg-white w-full sm:max-w-sm rounded-t-2xl sm:rounded-2xl p-6 space-y-4 shadow-xl">
                <div class="flex items-center justify-between">
                    <h3 class="text-lg font-bold text-gray-800">Cambiar contraseña</h3>
                    <button type="button" onclick="cerrarCambioPassword()" class="text-gray-400 hover:text-gray-700 text-2xl leading-none" aria-label="Cerrar">×</button>
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Contraseña actual</label>
                    <input type="password" id="pw_actual" required autocomplete="current-password" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Nueva contraseña</label>
                    <input type="password" id="pw_nueva" required minlength="6" autocomplete="new-password" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <div>
                    <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Confirmar nueva contraseña</label>
                    <input type="password" id="pw_nueva2" required minlength="6" autocomplete="new-password" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none">
                </div>
                <p id="pw_mensaje" class="hidden text-sm font-semibold rounded-lg p-3"></p>
                <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl">Guardar contraseña</button>
            </form>
        </div>`);
    document.getElementById('pw_actual').focus();
    document.getElementById('form-password').addEventListener('submit', guardarPassword);
};

window.cerrarCambioPassword = function() {
    const modal = document.getElementById('modal-password');
    if (modal) modal.remove();
};

async function guardarPassword(e) {
    e.preventDefault();
    const mensaje = document.getElementById('pw_mensaje');
    const mostrar = (texto, ok) => {
        mensaje.textContent = texto;
        mensaje.className = `text-sm font-semibold rounded-lg p-3 ${ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`;
    };
    const nueva = document.getElementById('pw_nueva').value;
    if (nueva !== document.getElementById('pw_nueva2').value) return mostrar('Las contraseñas nuevas no coinciden.', false);

    const boton = e.target.querySelector('button[type="submit"]');
    boton.disabled = true;
    try {
        const r = await api('/auth/cambiar-password', { method: 'POST', body: { actual: document.getElementById('pw_actual').value, nueva } });
        mostrar(r.mensaje, true);
        setTimeout(cerrarCambioPassword, 1500);
    } catch (err) {
        mostrar(err.message, false);
    } finally {
        boton.disabled = false;
    }
}
