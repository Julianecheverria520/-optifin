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
        personasAbiertas.add(normalizar(persona));
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

// Radar agrupado por persona (acordeón): arriba el total con cada una, al abrir el detalle de sus deudas
const personasAbiertas = new Set();

window.alternarPersona = function(clave) {
    if (personasAbiertas.has(clave)) personasAbiertas.delete(clave); else personasAbiertas.add(clave);
    dibujarTodo();
};

function filaDeuda(d) {
    const pagada = d.Estado === 'Pagada';
    const meDebe = d.Tipo_Deuda === 'Me debe';
    const acciones = d.Es_Propia === false
        // La registró la otra persona: aquí solo se ve; los abonos los registra ella (o se cruzan)
        ? `<span class="text-xs text-gray-400">Registrada por ${esc(d.Persona)}</span>`
        : `${pagada ? '' : `<button type="button" onclick="abrirAbono(${d.ID_Deuda})" class="text-green-700 hover:text-green-900 font-bold text-xs bg-green-50 px-3 py-1 rounded-lg">Abonar</button>`}
           <button type="button" onclick="editarDeuda(${d.ID_Deuda})" class="text-blue-700 hover:text-blue-900 font-bold text-xs bg-blue-50 px-3 py-1 rounded-lg">Editar</button>
           <button type="button" onclick="eliminarDeuda(${d.ID_Deuda})" class="text-red-600 hover:text-red-800 font-bold text-xs bg-red-50 px-3 py-1 rounded-lg">Eliminar</button>`;
    return `
        <div class="py-3 flex flex-wrap items-center justify-between gap-3 ${pagada ? 'opacity-60' : ''}">
            <div class="min-w-0">
                <p class="text-sm font-medium text-gray-800">
                    <span class="${meDebe ? 'text-green-700' : 'text-red-600'} font-bold">${meDebe ? 'Te debe' : 'Le debes'}</span>
                    ${esc(d.Descripcion || 'Sin nota')}
                </p>
                <p class="text-xs text-gray-400">${esc(d.Fecha_Creacion)}${d.ID_Transaccion ? ' · gasto compartido' : ''}${d.ID_Cuenta ? ' · ' + esc(nombreCuenta(d.ID_Cuenta)) : ''}</p>
            </div>
            <div class="flex flex-wrap items-center gap-3 text-sm">
                <div class="text-right">
                    <p class="font-bold text-gray-800">${formatoMoneda(d.Saldo_Pendiente)}</p>
                    <p class="text-xs text-gray-400">de ${formatoMoneda(d.Monto)}${d.Abonado > 0 ? ` · abonado ${formatoMoneda(d.Abonado)}` : ''}</p>
                </div>
                <span class="text-xs font-bold px-2 py-1 rounded ${CLASE_ESTADO[d.Estado] || ''}">${esc(d.Estado)}</span>
                <div class="flex gap-1 whitespace-nowrap">${acciones}</div>
            </div>
        </div>`;
}

function dibujarDeudas(deudas) {
    const cont = document.getElementById('lista_personas');
    if (deudas.length === 0) {
        const mensaje = deudasCargadas.length === 0 ? 'No hay deudas registradas.' : 'No hay deudas con estos filtros.';
        cont.innerHTML = `<p class="py-6 text-center text-gray-400 italic">${mensaje}</p>`;
        return;
    }

    const grupos = new Map();
    for (const d of deudas) {
        const clave = normalizar(d.Persona);
        const g = grupos.get(clave) || { clave, nombre: String(d.Persona).trim(), usuario: false, meDebe: 0, leDebo: 0, pendientes: 0, deudas: [] };
        g.usuario = g.usuario || Boolean(d.ID_Usuario_Contraparte);
        if (d.Tipo_Deuda === 'Me debe') g.meDebe += d.Saldo_Pendiente; else g.leDebo += d.Saldo_Pendiente;
        if (d.Estado !== 'Pagada') g.pendientes++;
        g.deudas.push(d);
        grupos.set(clave, g);
    }
    // Con una sola persona en pantalla (p. ej. filtrada), su detalle se abre solo
    if (grupos.size === 1) personasAbiertas.add([...grupos.keys()][0]);

    const ordenados = [...grupos.values()].sort((a, b) =>
        Math.abs(b.meDebe - b.leDebo) - Math.abs(a.meDebe - a.leDebo) || a.nombre.localeCompare(b.nombre));
    cont.innerHTML = ordenados.map(g => {
        const neto = g.meDebe - g.leDebo;
        const abierto = personasAbiertas.has(g.clave);
        const resumen = Math.abs(neto) < 0.5
            ? '<span class="text-gray-500 font-bold">A paz y salvo</span>'
            : `<span class="font-bold ${neto > 0 ? 'text-green-700' : 'text-red-600'}">${neto > 0 ? 'Te debe' : 'Le debes'} ${formatoMoneda(Math.abs(neto))}</span>`;
        const desglose = g.meDebe > 0 && g.leDebo > 0
            ? `<span class="block text-xs text-gray-400">Te debe ${formatoMoneda(g.meDebe)} · le debes ${formatoMoneda(g.leDebo)}</span>` : '';
        const deudasOrdenadas = [...g.deudas].sort((a, b) =>
            (a.Estado === 'Pagada') - (b.Estado === 'Pagada') || String(b.Fecha_Creacion).localeCompare(String(a.Fecha_Creacion)));
        return `
            <div class="rounded-xl border border-gray-200 overflow-hidden">
                <button type="button" onclick="alternarPersona('${esc(g.clave)}')" aria-expanded="${abierto}" class="w-full flex flex-wrap items-center justify-between gap-3 p-4 text-left hover:bg-gray-50">
                    <div class="flex items-center gap-3 min-w-0">
                        <svg class="w-4 h-4 text-gray-400 shrink-0 transition-transform ${abierto ? 'rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                        <div class="min-w-0">
                            <p class="font-semibold text-gray-800 truncate">${esc(g.nombre)}
                                ${g.usuario ? '<span class="ml-1 text-[10px] font-bold uppercase bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Usuario OptiFin</span>' : ''}</p>
                            <p class="text-xs text-gray-400">${g.pendientes} ${g.pendientes === 1 ? 'deuda pendiente' : 'deudas pendientes'} · ${g.deudas.length} en total</p>
                        </div>
                    </div>
                    <div class="text-right text-sm">${resumen}${desglose}</div>
                </button>
                <div class="${abierto ? '' : 'hidden'} border-t border-gray-100 px-4 divide-y divide-gray-100">
                    ${deudasOrdenadas.map(filaDeuda).join('')}
                </div>
            </div>`;
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
        if (idDeudaEditando === id) salirDeEdicionDeuda();
        cargarTodo();
    } catch (err) {
        alert(err.message);
    }
}

// ---------- Formulario: registrar o editar ----------

let idDeudaEditando = null;
const CAMPOS_DEL_MOVIMIENTO = ['tipo_deuda', 'fecha_deuda', 'cuenta_deuda'];

window.editarDeuda = function(id) {
    const d = deudasCargadas.find(x => x.ID_Deuda === id);
    if (!d) return;
    idDeudaEditando = id;
    document.getElementById('persona_deuda').value = d.Persona;
    document.getElementById('tipo_deuda').value = d.Tipo_Deuda;
    document.getElementById('monto_deuda').value = d.Monto;
    document.getElementById('fecha_deuda').value = String(d.Fecha_Creacion).slice(0, 10);
    document.getElementById('cuenta_deuda').value = d.ID_Cuenta || '';
    document.getElementById('nota_deuda').value = d.Descripcion || '';

    // Las deudas de un gasto compartido siguen a su movimiento: tipo, fecha y cuenta no se cambian aquí
    const vinculada = Boolean(d.ID_Transaccion);
    const pagadaPorOtro = vinculada && d.Tipo_Deuda === 'Le debo';
    for (const campo of CAMPOS_DEL_MOVIMIENTO) document.getElementById(campo).disabled = vinculada;
    document.getElementById('monto_deuda').disabled = pagadaPorOtro;
    const aviso = document.getElementById('aviso_deuda_vinculada');
    aviso.classList.toggle('hidden', !vinculada);
    aviso.innerText = pagadaPorOtro
        ? 'Esta deuda viene de un gasto que otra persona pagó por ti: aquí puedes cambiar la persona y la nota. Para cambiar el valor, anula el movimiento y regístralo de nuevo.'
        : 'Esta deuda es una parte de un gasto compartido: puedes cambiar la persona, el valor de su parte y la nota. La fecha sigue a la del movimiento.';

    document.getElementById('titulo_form_deuda').innerText = 'Editar Deuda';
    document.getElementById('btn_guardar_deuda').innerText = 'Guardar cambios';
    document.getElementById('btn_cancelar_deuda').classList.remove('hidden');
    document.getElementById('deudasForm').scrollIntoView({ behavior: 'smooth', block: 'center' });
};

function salirDeEdicionDeuda() {
    idDeudaEditando = null;
    document.getElementById('deudasForm').reset();
    for (const campo of [...CAMPOS_DEL_MOVIMIENTO, 'monto_deuda']) document.getElementById(campo).disabled = false;
    document.getElementById('aviso_deuda_vinculada').classList.add('hidden');
    document.getElementById('titulo_form_deuda').innerText = 'Registrar Deuda';
    document.getElementById('btn_guardar_deuda').innerText = 'Registrar en Radar';
    document.getElementById('btn_cancelar_deuda').classList.add('hidden');
    document.getElementById('fecha_deuda').value = fechaHoyISO();
}

document.getElementById('btn_cancelar_deuda').addEventListener('click', salirDeEdicionDeuda);

document.getElementById('deudasForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const cuenta = document.getElementById('cuenta_deuda').value;
    const d = {
        persona: document.getElementById('persona_deuda').value,
        tipo_deuda: document.getElementById('tipo_deuda').value,
        monto: parseFloat(document.getElementById('monto_deuda').value),
        fecha_creacion: document.getElementById('fecha_deuda').value,
        id_cuenta: cuenta ? parseInt(cuenta) : null,
        descripcion: document.getElementById('nota_deuda').value,
    };
    try {
        if (idDeudaEditando) {
            await api(`${RUTA_DEUDAS}${idDeudaEditando}`, { method: "PUT", body: d });
        } else {
            await api(RUTA_DEUDAS, { method: "POST", body: d });
        }
        salirDeEdicionDeuda();
        cargarTodo();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('fecha_deuda').value = fechaHoyISO();
cargarTodo().then(aplicarFiltrosDeUrl);
cargarLiquidaciones();
