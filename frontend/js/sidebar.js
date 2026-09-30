function cargarSidebar(paginaActiva) {
    // Sin sesión, config.js ya está redirigiendo al login
    if (!USUARIO_ACTUAL) return;

    const sidebarHTML = `
        <div class="flex flex-col h-full bg-[#111c43] text-white w-64 shadow-xl font-sans">
            <!-- Logo y Título -->
            <div class="p-6 pt-8 pb-8">
                <div class="flex items-center gap-3 mb-1">
                    <svg class="w-8 h-8 text-blue-400" fill="currentColor" viewBox="0 0 24 24"><path d="M3 13h2v8H3zm4-5h2v13H7zm4 4h2v9h-2zm4-6h2v15h-2zm4-4h2v19h-2z"/></svg>
                    <h1 class="text-2xl font-bold tracking-wide">OptiFin</h1>
                </div>
                <p class="text-gray-400 text-xs ml-11">Tu dinero, en orden</p>
            </div>

            <!-- Navegación -->
            <nav class="flex-1 px-4 space-y-1 mt-4">
                <a href="dashboard.html" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === 'dashboard' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
                    <span class="text-sm font-medium">Resumen</span>
                </a>
                
                <a href="index.html" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === 'transacciones' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    <span class="text-sm font-medium">Movimientos</span>
                </a>

                <a href="planificacion.html" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === 'planificacion' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"></path></svg>
                    <span class="text-sm font-medium">Presupuesto</span>
                </a>

                <a href="deudas.html" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === 'deudas' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                    <span class="text-sm font-medium">Deudas</span>
                </a>
                
                <div class="mt-8 mb-4 px-4"><hr class="border-[#1a295c]"></div>

                <a href="configuracion.html" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === 'configuracion' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path></svg>
                    <span class="text-sm font-medium">Cuentas</span>
                </a>
                
                <a href="categorias.html" class="flex items-center gap-3 py-3 px-4 rounded-xl transition-all duration-200 ${paginaActiva === 'categorias' ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:bg-[#1a295c] hover:text-white'}">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    <span class="text-sm font-medium">Categorías</span>
                </a>
            </nav>

            <!-- Usuario Bottom -->
            <div class="mt-auto p-4 mb-4">
                <div class="flex items-center gap-3 p-3 rounded-xl hover:bg-[#1a295c] transition-all duration-200">
                    <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold text-white shadow">${esc(USUARIO_ACTUAL.nombre.charAt(0))}</div>
                    <div class="flex-1">
                        <p class="text-sm font-medium text-white truncate">${esc(USUARIO_ACTUAL.nombre)}</p>
                    </div>
                    <button onclick="cerrarSesion()" class="text-gray-400 hover:text-red-400 transition-colors" title="Cerrar sesión">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                    </button>
                </div>
            </div>

        </div>
    `;

    document.getElementById('sidebar-container').innerHTML = sidebarHTML;
}