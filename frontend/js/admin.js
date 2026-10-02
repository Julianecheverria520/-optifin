// Panel de administración. El servidor es quien valida que seas administrador (403 si no);
// aquí solo se redirige al Resumen para no mostrar una página vacía.

let idClave = null;

async function cargarUsuarios() {
    const tabla = document.getElementById('tabla_usuarios');
    tabla.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-gray-400">Cargando usuarios...</td></tr>';
    let usuarios;
    try {
        usuarios = await api('/admin/usuarios');
    } catch (err) {
        if (err.status === 403) return window.location.replace('dashboard.html');
        tabla.innerHTML = `<tr><td colspan="4" class="text-center py-6 text-red-500 font-bold">${esc(err.message)}</td></tr>`;
        return;
    }

    tabla.innerHTML = usuarios.map(u => {
        const ingreso = u.ultimo_ingreso ? new Date(u.ultimo_ingreso).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : 'Nunca';
        const estado = !u.activo ? ['bg-red-100', 'Suspendido'] : !u.confirmado ? ['bg-yellow-100', 'Sin confirmar'] : ['bg-green-100', 'Activo'];
        const botonEstado = u.es_tu_cuenta ? ''
            : `<button type="button" onclick="cambiarEstado('${esc(u.id)}', ${!u.activo})" class="ml-1 font-bold text-xs bg-gray-100 px-3 py-1.5 rounded-lg">${u.activo ? 'Suspender' : 'Reactivar'}</button>`;
        return `
            <tr class="border-b border-gray-100">
                <td class="py-3 px-4">
                    <div class="font-bold text-gray-800">${esc(u.nombre)}${u.es_tu_cuenta ? ' <span class="text-xs text-gray-400 font-normal">(tú)</span>' : ''}</div>
                    <div class="text-xs text-gray-400">${esc(u.email)}</div>
                </td>
                <td class="py-3 px-4 text-gray-600">${esc(ingreso)}</td>
                <td class="py-3 px-4"><span class="px-2.5 py-1 text-xs font-bold rounded-lg ${estado[0]}">${estado[1]}</span></td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                    <button type="button" onclick="abrirModalClave('${esc(u.id)}', '${esc(u.nombre)}')" class="font-bold text-xs bg-blue-100 px-3 py-1.5 rounded-lg">Contraseña</button>
                    ${botonEstado}
                </td>
            </tr>`;
    }).join('') || '<tr><td colspan="4" class="text-center py-6 text-gray-400">No hay usuarios</td></tr>';
}

window.abrirModalClave = function(id, nombre) {
    idClave = id;
    document.getElementById('clave_para').textContent = nombre;
    document.getElementById('clave_nueva').value = '';
    document.getElementById('modal_clave').classList.remove('hidden');
    document.getElementById('clave_nueva').focus();
};

window.cerrarModalClave = function() {
    idClave = null;
    document.getElementById('modal_clave').classList.add('hidden');
};

document.getElementById('form_clave').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        await api(`/admin/usuarios/${idClave}/password`, { method: 'PUT', body: { password: document.getElementById('clave_nueva').value } });
        cerrarModalClave();
        alert('Contraseña actualizada.');
    } catch (err) {
        alert(err.message);
    }
});

window.cambiarEstado = async function(id, activar) {
    if (!confirm(`¿Seguro que deseas ${activar ? 'reactivar' : 'suspender'} a este usuario?`)) return;
    try {
        await api(`/admin/usuarios/${id}/estado`, { method: 'PUT', body: { activo: activar } });
        cargarUsuarios();
    } catch (err) {
        alert(err.message);
    }
};

cargarUsuarios();
