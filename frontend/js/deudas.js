const RUTA_DEUDAS = "/deudas/";
const RUTA_CUENTAS = "/cuentas/";

let deudasCargadas = [];
let cuentas = [];
let idDeudaAbonando = null;

const CLASE_ESTADO = {
    Pendiente: "bg-gray-100 text-gray-700",
    Parcial: "bg-yellow-100 text-yellow-800",
    Pagada: "bg-green-100 text-green-800",
};

function nombreCuenta(id) {
    if (!id) return "-";
    const c = cuentas.find(x => x.id_cuenta === id);
    return c ? c.nombre : "?";
}

function opcionesCuentas() {
    return `<option value="">Ninguna (sin movimiento de dinero)</option>` +
        cuentas.map(c => `<option value="${c.id_cuenta}">${esc(c.nombre)} (${formatoMoneda(c.saldo_actual)})</option>`).join('');
}

let abonosCargados = [];

async function cargarTodo() {
    try {
        [deudasCargadas, abonosCargados, cuentas] = await Promise.all([
            api(RUTA_DEUDAS), api(`${RUTA_DEUDAS}abonos`), api(RUTA_CUENTAS),
        ]);
    } catch (err) {
        return alert(err.message);
    }

    // Conservar la cuenta elegida en el formulario de nueva deuda
    const selectCuenta = document.getElementById('cuenta_deuda');
    const seleccionPrevia = selectCuenta.value;
    selectCuenta.innerHTML = opcionesCuentas();
    selectCuenta.value = cuentas.some(c => String(c.id_cuenta) === seleccionPrevia) ? seleccionPrevia : "";

    poblarFiltroPersonas();
    poblarCrucePersonas();
    dibujarTodo();
}

// ---------- Filtros ----------

const normalizar = texto => String(texto ?? '').trim().toLowerCase();

function poblarFiltroPersonas() {
    const select = document.getElementById('filtro_persona');
    const seleccionPrevia = select.value;
    // Una opción por persona (sin distinguir mayúsculas), con el nombre tal como se escribió la primera vez
    const porClave = new Map();
    for (const d of deudasCargadas) {
        if (!porClave.has(normalizar(d.Persona))) porClave.set(normalizar(d.Persona), String(d.Persona).trim());
    }
    const personas = [...porClave.values()].sort((a, b) => a.localeCompare(b));
    select.innerHTML = `<option value="">Todas</option>` + personas.map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
    select.value = personas.some(p => p === seleccionPrevia) ? seleccionPrevia : "";
}

function deudasFiltradas() {
    const persona = normalizar(document.getElementById('filtro_persona').value);
    const tipo = document.getElementById('filtro_tipo').value;
    const verPagadas = document.getElementById('filtro_pagadas').checked;
    return deudasCargadas.filter(d =>
        (!persona || normalizar(d.Persona) === persona) &&
        (!tipo || d.Tipo_Deuda === tipo) &&
        (verPagadas || d.Estado !== 'Pagada'));
}

function dibujarTodo() {
    const filtradas = deudasFiltradas();
    const pendiente = tipo => filtradas.filter(d => d.Tipo_Deuda === tipo).reduce((s, d) => s + d.Saldo_Pendiente, 0);
    document.getElementById('total_me_deben').innerText = formatoMoneda(pendiente('Me debe'));
    document.getElementById('total_debo').innerText = formatoMoneda(pendiente('Le debo'));

    dibujarDeudas(filtradas);
    // El historial muestra los abonos de las deudas visibles
    const idsVisibles = new Set(filtradas.map(d => d.ID_Deuda));
    dibujarAbonos(abonosCargados.filter(a => idsVisibles.has(a.ID_Deuda)));
}

// Filtros iniciales desde el Resumen: deudas.html?persona=Juan o ?tipo=Me%20debe
function aplicarFiltrosDeUrl() {
    const params = new URLSearchParams(window.location.search);
    const persona = params.get('persona');
    if (persona) {
        const select = document.getElementById('filtro_persona');
        const opcion = [...select.options].find(o => o.value && normalizar(o.value) === normalizar(persona));
        if (opcion) select.value = opcion.value;
    }
    if (['Me debe', 'Le debo'].includes(params.get('tipo'))) document.getElementById('filtro_tipo').value = params.get('tipo');
    dibujarTodo();

    // Desde el Resumen con ?cruce=1: abrir el cruce de cuentas con esa persona
    if (persona && params.get('cruce')) {
        const select = document.getElementById('cruce_persona');
        const opcion = [...select.options].find(o => o.value && normalizar(o.value) === normalizar(persona));
        if (opcion) {
            select.value = opcion.value;
            cargarVistaPreviaCruce();
        }
        document.getElementById('seccion_cruce').scrollIntoView({ block: 'start' });
    }
}

// ---------- Cruce de cuentas ----------

// Personas con saldo pendiente en ambos sentidos (las únicas con algo que cruzar)
function poblarCrucePersonas() {
    const saldos = new Map();
    for (const d of deudasCargadas) {
        if (d.Saldo_Pendiente <= 0) continue;
        const clave = normalizar(d.Persona);
        const s = saldos.get(clave) || { nombre: String(d.Persona).trim(), meDebe: 0, leDebo: 0 };
        if (d.Tipo_Deuda === 'Me debe') s.meDebe += d.Saldo_Pendiente; else s.leDebo += d.Saldo_Pendiente;
        saldos.set(clave, s);
    }
    const candidatas = [...saldos.values()].filter(s => s.meDebe > 0 && s.leDebo > 0).sort((a, b) => a.nombre.localeCompare(b.nombre));

    const select = document.getElementById('cruce_persona');
    const seleccionPrevia = select.value;
    select.innerHTML = candidatas.length === 0
        ? '<option value="">Nadie con deudas en ambos sentidos</option>'
        : '<option value="">Elige una persona…</option>' + candidatas.map(s => `<option value="${esc(s.nombre)}">${esc(s.nombre)}</option>`).join('');
    select.value = candidatas.some(s => s.nombre === seleccionPrevia) ? seleccionPrevia : '';
    cargarVistaPreviaCruce();
}

function listaDeudasCruce(titulo, deudas, clase) {
    const items = deudas.map(d => `
        <li class="flex justify-between gap-2 text-sm py-1">
            <span class="text-gray-600 truncate">${esc(d.descripcion || 'Sin descripción')} <span class="text-xs text-gray-400">${esc(d.fecha)}</span></span>
            <span class="font-semibold ${clase}">${formatoMoneda(d.saldo)}</span>
        </li>`).join('');
    return `<div class="rounded-lg border border-gray-200 p-3">
        <p class="text-xs font-bold uppercase text-gray-500 mb-1">${titulo}</p>
        <ul class="divide-y divide-gray-100">${items}</ul>
    </div>`;
}

async function cargarVistaPreviaCruce() {
    const persona = document.getElementById('cruce_persona').value;
    const cont = document.getElementById('cruce_vista_previa');
    if (!persona) {
        cont.innerHTML = '';
        return;
    }

    let v, liquidaciones;
    try {
        [v, liquidaciones] = await Promise.all([
            api(`/liquidaciones/vista-previa?persona=${encodeURIComponent(persona)}`),
            api('/liquidaciones/'),
        ]);
    } catch (err) {
        return alert(err.message);
    }

    const pendiente = liquidaciones.find(l => l.Estado === 'Pendiente' && normalizar(l.Persona) === normalizar(persona));
    const queda = v.neto >= 0
        ? `${esc(persona)} te queda debiendo <b class="text-green-700">${formatoMoneda(v.neto)}</b>`
        : `Le quedas debiendo a ${esc(persona)} <b class="text-red-600">${formatoMoneda(-v.neto)}</b>`;
    const accion = pendiente
        ? `<p class="text-sm font-semibold text-yellow-700 bg-yellow-50 rounded p-2">Ya hay un cruce pendiente con ${esc(persona)} (ver historial).</p>`
        : `<button type="button" onclick="proponerCruce()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded">
               ${v.requiere_aprobacion ? `Proponer cruce a ${esc(persona)}` : 'Aplicar cruce'}
           </button>
           ${v.requiere_aprobacion ? `<span class="text-xs text-gray-400 ml-2">${esc(persona)} es usuaria de OptiFin: deberá aprobarlo.</span>` : ''}`;

    cont.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            ${listaDeudasCruce(`${esc(persona)} te debe · ${formatoMoneda(v.total_me_deben)}`, v.me_deben, 'text-green-700')}
            ${listaDeudasCruce(`Tú le debes · ${formatoMoneda(v.total_debo)}`, v.debo, 'text-red-600')}
        </div>
        <div class="rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900 mb-3">
            Se compensan <b>${formatoMoneda(v.monto_cruzado)}</b> en ambos lados. Después del cruce: ${queda}.
            <span class="block text-xs text-indigo-700 mt-1">No mueve dinero de tus cuentas; ese saldo final lo pagan después con "Abonar".</span>
        </div>
        ${accion}`;
}

window.proponerCruce = async function() {
    const persona = document.getElementById('cruce_persona').value;
    if (!persona) return;
    try {
        const r = await api('/liquidaciones/', { method: "POST", body: { persona } });
        alert(r.mensaje);
        await cargarTodo();
        cargarLiquidaciones();
    } catch (err) {
        alert(err.message);
    }
}

const CLASE_LIQUIDACION = {
    Pendiente: 'bg-yellow-100 text-yellow-800',
    Aplicada: 'bg-green-100 text-green-800',
    Rechazada: 'bg-red-100 text-red-800',
    Anulada: 'bg-gray-200 text-gray-600',
};

async function cargarLiquidaciones() {
    let liquidaciones;
    try {
        liquidaciones = await api('/liquidaciones/');
    } catch (err) {
        return alert(err.message);
    }
    const cont = document.getElementById('lista_liquidaciones');
    if (liquidaciones.length === 0) {
        cont.innerHTML = '<p class="text-sm text-gray-400 italic py-2">Aún no hay cruces.</p>';
        return;
    }

    cont.innerHTML = liquidaciones.map(l => {
        const neto = l.Neto >= 0
            ? `${esc(l.Persona)} te debe ${formatoMoneda(l.Neto)}`
            : `le debes ${formatoMoneda(-l.Neto)} a ${esc(l.Persona)}`;
        // El backend entrega cada cruce visto desde mi lado; quien lo propuso puede anularlo,
        // y la otra persona lo aprueba o rechaza desde su propia sesión
        let acciones = '';
        if (l.Estado === 'Pendiente') {
            acciones = l.Soy_Proponente
                ? `<span class="text-xs text-yellow-700">Esperando aprobación de ${esc(l.Persona)}</span>
                   <button type="button" onclick="accionLiquidacion(${l.ID_Liquidacion}, 'anular')" class="text-xs font-bold text-gray-700 bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded">Anular</button>`
                : `<span class="text-xs text-yellow-700">${esc(l.Persona)} te propone este cruce</span>
                   <button type="button" onclick="accionLiquidacion(${l.ID_Liquidacion}, 'aprobar')" class="text-xs font-bold text-white bg-green-600 hover:bg-green-700 px-2 py-1 rounded">Aprobar</button>
                   <button type="button" onclick="accionLiquidacion(${l.ID_Liquidacion}, 'rechazar')" class="text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 px-2 py-1 rounded">Rechazar</button>`;
        }

        return `
            <div class="py-3 flex flex-wrap items-start justify-between gap-2 ${l.Estado === 'Pendiente' && !l.Soy_Proponente ? 'bg-yellow-50 -mx-2 px-2 rounded' : ''}">
                <div class="text-sm">
                    <p class="font-medium text-gray-800">Cruce #${l.ID_Liquidacion} con ${esc(l.Persona)} <span class="text-xs text-gray-400 font-normal">${esc(l.Fecha)}${l.Soy_Proponente ? '' : ' · lo propuso ' + esc(l.Persona)}</span></p>
                    <p class="text-gray-600">Te debía ${formatoMoneda(l.Total_Me_Deben)} · le debías ${formatoMoneda(l.Total_Debo)} → se compensan <b>${formatoMoneda(l.Monto_Cruzado)}</b>; queda: ${neto}</p>
                </div>
                <div class="flex flex-wrap items-center justify-end gap-2 max-w-md">
                    <span class="text-xs font-bold px-2 py-1 rounded ${CLASE_LIQUIDACION[l.Estado] || ''}">${esc(l.Estado)}</span>
                    ${acciones}
                </div>
            </div>`;
    }).join('');
}

window.accionLiquidacion = async function(id, accion) {
    const textos = { aprobar: '¿Aprobar este cruce? Se aplicará a las deudas de ambos.', rechazar: '¿Rechazar este cruce?', anular: '¿Anular este cruce?' };
    if (!confirm(textos[accion])) return;
    try {
        const r = await api(`/liquidaciones/${id}/${accion}`, { method: "POST" });
        alert(r.mensaje);
        await cargarTodo();
        cargarLiquidaciones();
    } catch (err) {
        alert(err.message);
    }
}

document.getElementById('cruce_persona').addEventListener('change', cargarVistaPreviaCruce);

for (const id of ['filtro_persona', 'filtro_tipo', 'filtro_pagadas']) {
    document.getElementById(id).addEventListener('change', dibujarTodo);
}
document.getElementById('btn_limpiar_filtros').addEventListener('click', () => {
    document.getElementById('filtro_persona').value = '';
    document.getElementById('filtro_tipo').value = '';
    document.getElementById('filtro_pagadas').checked = false;
    history.replaceState(null, '', window.location.pathname);
    dibujarTodo();
});

// ---------- Tablas ----------

function dibujarDeudas(deudas) {
    const tabla = document.getElementById('tablaDeudas');
    if (deudas.length === 0) {
        const mensaje = deudasCargadas.length === 0 ? 'No hay deudas registradas.' : 'No hay deudas con estos filtros.';
        tabla.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-gray-400 italic">${mensaje}</td></tr>`;
        return;
    }

    // Primero las que tienen saldo pendiente
    const ordenadas = [...deudas].sort((a, b) => (a.Estado === 'Pagada') - (b.Estado === 'Pagada'));

    tabla.innerHTML = ordenadas.map(d => {
        const pagada = d.Estado === 'Pagada';
        return `
        <tr class="border-b hover:bg-gray-100 ${pagada ? 'opacity-50' : ''}">
            <td class="py-3 px-6">
                <span class="font-medium">${esc(d.Persona)}</span>
                ${d.ID_Usuario_Contraparte ? '<span class="ml-1 text-[10px] font-bold uppercase bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Usuario OptiFin</span>' : ''}
                ${d.Descripcion || d.ID_Transaccion ? `<span class="block text-xs text-gray-400">${esc(d.Descripcion || '')}${d.ID_Transaccion ? ' · gasto compartido' : ''}</span>` : ''}
            </td>
            <td class="py-3 px-6">
                <span class="${d.Tipo_Deuda === 'Me debe' ? 'bg-green-100 text-green-800 border border-green-300' : 'bg-red-100 text-red-800 border border-red-300'} py-1 px-3 rounded text-xs font-bold">
                    ${esc(d.Tipo_Deuda)}
                </span>
            </td>
            <td class="py-3 px-6">${formatoMoneda(d.Monto)}</td>
            <td class="py-3 px-6">${formatoMoneda(d.Abonado)}</td>
            <td class="py-3 px-6 font-bold">${formatoMoneda(d.Saldo_Pendiente)}</td>
            <td class="py-3 px-6">${esc(d.Fecha_Creacion)}</td>
            <td class="py-3 px-6"><span class="text-xs font-bold px-2 py-1 rounded ${CLASE_ESTADO[d.Estado] || ''}">${esc(d.Estado)}</span></td>
            <td class="py-3 px-6 whitespace-nowrap">
                ${d.Es_Propia === false
                    // La registró la otra persona: aquí solo se ve; los abonos los registra ella (o se cruzan)
                    ? `<span class="text-xs text-gray-400">Registrada por ${esc(d.Persona)}</span>`
                    : `${pagada ? '' : `<button type="button" onclick="abrirAbono(${d.ID_Deuda})" class="text-green-700 hover:text-green-900 font-bold text-xs bg-green-50 px-3 py-1 rounded-lg">Abonar</button>`}
                       <button type="button" onclick="eliminarDeuda(${d.ID_Deuda})" class="text-red-600 hover:text-red-800 font-bold text-xs bg-red-50 px-3 py-1 rounded-lg ml-1">Eliminar</button>`}
            </td>
        </tr>`;
    }).join('');
}

function dibujarAbonos(abonos) {
    const tabla = document.getElementById('tablaAbonos');
    if (abonos.length === 0) {
        tabla.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-gray-400 italic">Aún no hay abonos.</td></tr>';
        return;
    }

    abonos.sort((a, b) => String(b.Fecha).localeCompare(String(a.Fecha)) || b.ID_Abono - a.ID_Abono);
    tabla.innerHTML = abonos.map(a => {
        const deuda = deudasCargadas.find(d => d.ID_Deuda === a.ID_Deuda);
        // Los abonos de un cruce se gestionan como un todo: no se eliminan sueltos
        const esCruce = String(a.Descripcion || '').startsWith('Cruce de cuentas');
        const origen = a.ID_Cuenta ? nombreCuenta(a.ID_Cuenta) : (a.Descripcion || '-');
        return `
        <tr class="border-b hover:bg-gray-100">
            <td class="py-3 px-6">${esc(a.Fecha)}</td>
            <td class="py-3 px-6 font-medium">${esc(deuda ? deuda.Persona : '?')}</td>
            <td class="py-3 px-6 font-bold">${formatoMoneda(a.Monto)}</td>
            <td class="py-3 px-6 ${esCruce ? 'text-indigo-700 font-medium' : ''}">${esc(origen)}</td>
            <td class="py-3 px-6">
                ${esCruce ? '<span class="text-xs text-gray-400">Parte de un cruce</span>' : `<button type="button" onclick="eliminarAbono(${a.ID_Abono})" class="text-red-600 hover:text-red-800 font-bold text-xs bg-red-50 px-3 py-1 rounded-lg">Eliminar</button>`}
            </td>
        </tr>`;
    }).join('');
}

// ---------- Abonos ----------

window.abrirAbono = function(id) {
    const d = deudasCargadas.find(x => x.ID_Deuda === id);
    if (!d) return;
    idDeudaAbonando = id;

    const meDebe = d.Tipo_Deuda === 'Me debe';
    document.getElementById('abono_info').innerText =
        `${d.Persona} · ${meDebe ? 'te debe' : 'le debes'} ${formatoMoneda(d.Saldo_Pendiente)} de ${formatoMoneda(d.Monto)}`;
    document.getElementById('lbl_cuenta_abono').innerText = meDebe ? 'Cuenta donde recibes' : 'Cuenta desde donde pagas';
    document.getElementById('cuenta_abono').innerHTML = opcionesCuentas();
    document.getElementById('monto_abono').value = d.Saldo_Pendiente;
    document.getElementById('monto_abono').max = d.Saldo_Pendiente;
    document.getElementById('fecha_abono').value = fechaHoyISO();

    const panel = document.getElementById('panelAbono');
    panel.classList.remove('hidden');
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function cerrarAbono() {
    idDeudaAbonando = null;
    document.getElementById('abonoForm').reset();
    document.getElementById('panelAbono').classList.add('hidden');
}

document.getElementById('btn_cancelar_abono').addEventListener('click', cerrarAbono);

document.getElementById('abonoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const cuenta = document.getElementById('cuenta_abono').value;
    const abono = {
        fecha: document.getElementById('fecha_abono').value,
        monto: parseFloat(document.getElementById('monto_abono').value),
        id_cuenta: cuenta ? parseInt(cuenta) : null,
    };
    try {
        await api(`${RUTA_DEUDAS}${idDeudaAbonando}/abonos`, { method: "POST", body: abono });
        cerrarAbono();
        cargarTodo();
    } catch (err) {
        alert(err.message);
    }
});

window.eliminarAbono = async function(id) {
    if (!confirm("¿Eliminar este abono? El saldo de la deuda y de la cuenta se recalcularán.")) return;
    try {
        await api(`${RUTA_DEUDAS}abonos/${id}`, { method: "DELETE" });
        cargarTodo();
    } catch (err) {
        alert(err.message);
    }
}

// ---------- Deudas ----------

window.eliminarDeuda = async function(id) {
    const d = deudasCargadas.find(x => x.ID_Deuda === id);
    const aviso = d && d.ID_Transaccion
        ? "Esta deuda viene de un gasto compartido. Si la eliminas (p. ej. la perdonas), esa parte pasa a ser gasto tuyo.\n¿Eliminarla junto con sus abonos?"
        : "¿Eliminar esta deuda y todos sus abonos?";
    if (!confirm(aviso)) return;
    try {
        await api(`${RUTA_DEUDAS}${id}`, { method: "DELETE" });
        if (idDeudaAbonando === id) cerrarAbono();
        cargarTodo();
    } catch (err) {
        alert(err.message);
    }
}

document.getElementById('deudasForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const cuenta = document.getElementById('cuenta_deuda').value;
    const d = {
        persona: document.getElementById('persona_deuda').value,
        tipo_deuda: document.getElementById('tipo_deuda').value,
        monto: parseFloat(document.getElementById('monto_deuda').value),
        fecha_creacion: document.getElementById('fecha_deuda').value,
        id_cuenta: cuenta ? parseInt(cuenta) : null,
    };
    try {
        await api(RUTA_DEUDAS, { method: "POST", body: d });
        document.getElementById('deudasForm').reset();
        document.getElementById('fecha_deuda').value = fechaHoyISO();
        cargarTodo();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('fecha_deuda').value = fechaHoyISO();
cargarTodo().then(aplicarFiltrosDeUrl);
cargarLiquidaciones();
