const RUTA_CUENTAS = "/cuentas/";

let cuentasCargadas = [];
let idCuentaEditando = null; // null = creando una cuenta nueva

async function cargarCuentas() {
    try {
        cuentasCargadas = await api(RUTA_CUENTAS);
    } catch (err) {
        return alert(err.message);
    }

    const tabla = document.getElementById('tablaCuentas');
    if (cuentasCargadas.length === 0) {
        tabla.innerHTML = '<tr><td colspan="4" class="py-6 text-center text-gray-400 italic">Aún no hay cuentas.</td></tr>';
        return;
    }

    tabla.innerHTML = cuentasCargadas.map(c => `
        <tr class="border-b hover:bg-gray-50">
            <td class="py-3 px-6">${esc(c.nombre)}</td>
            <td class="py-3 px-6 text-gray-500 text-xs">${esc(c.tipo)}</td>
            <td class="py-3 px-6 text-right font-bold text-lg ${c.saldo_actual < 0 ? 'text-red-600' : 'text-green-700'}">
                ${formatoMoneda(c.saldo_actual)}
                ${c.tipo === 'Crédito' && c.saldo_actual < 0 ? '<span class="block text-xs font-normal text-gray-400">por pagar</span>' : ''}
            </td>
            <td class="py-3 px-6 text-right whitespace-nowrap">
                <button type="button" onclick="prepararEdicionCuenta(${c.id_cuenta})" class="text-blue-600 hover:text-blue-800 font-bold text-xs bg-blue-50 px-3 py-1 rounded-lg">Editar</button>
                <button type="button" onclick="eliminarCuenta(${c.id_cuenta})" class="text-red-600 hover:text-red-800 font-bold text-xs bg-red-50 px-3 py-1 rounded-lg ml-1">Eliminar</button>
            </td>
        </tr>
    `).join('');
}

function salirDeEdicion() {
    idCuentaEditando = null;
    document.getElementById('cuentaForm').reset();
    document.getElementById('titulo_form_cuenta').innerText = "Añadir Cuenta";
    document.getElementById('btn_guardar_cuenta').innerText = "Crear Cuenta";
    document.getElementById('btn_cancelar_cuenta').classList.add('hidden');
}

window.prepararEdicionCuenta = function(id) {
    const c = cuentasCargadas.find(x => x.id_cuenta === id);
    if (!c) return;
    idCuentaEditando = id;
    document.getElementById('nombre_cuenta').value = c.nombre;
    document.getElementById('tipo_cuenta').value = c.tipo;
    document.getElementById('saldo_inicial').value = c.saldo_inicial;
    document.getElementById('titulo_form_cuenta').innerText = "Editar Cuenta";
    document.getElementById('btn_guardar_cuenta').innerText = "Actualizar Cuenta";
    document.getElementById('btn_cancelar_cuenta').classList.remove('hidden');
    document.getElementById('cuentaForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

window.eliminarCuenta = async function(id) {
    if (!confirm("¿Eliminar esta cuenta?")) return;
    try {
        await api(`${RUTA_CUENTAS}${id}`, { method: "DELETE" });
        if (idCuentaEditando === id) salirDeEdicion();
        cargarCuentas();
    } catch (err) {
        alert(err.message);
    }
}

document.getElementById('btn_cancelar_cuenta').addEventListener('click', salirDeEdicion);

document.getElementById('cuentaForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const c = {
        nombre_cuenta: document.getElementById('nombre_cuenta').value,
        tipo_cuenta: document.getElementById('tipo_cuenta').value,
        saldo_inicial: parseFloat(document.getElementById('saldo_inicial').value)
    };

    try {
        if (idCuentaEditando !== null) {
            await api(`${RUTA_CUENTAS}${idCuentaEditando}`, { method: "PUT", body: c });
        } else {
            await api(RUTA_CUENTAS, { method: "POST", body: c });
        }
        salirDeEdicion();
        cargarCuentas();
    } catch (err) {
        alert(err.message);
    }
});

cargarCuentas();
