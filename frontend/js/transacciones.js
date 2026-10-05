const RUTA_TRANS = "/transacciones/";
const RUTA_CAT = "/categorias/";
const RUTA_CUENTAS = "/cuentas/";

let todasLasSubcategorias = [];
let todasLasCategorias = [];
let todasLasCuentas = [];
let categoriaSeleccionada = null; // ID de la categoría activa en la grilla

// Carga inicial de la página
async function cargarConfiguracion() {
    try {
        const dataCat = await api(RUTA_CAT);
        todasLasCategorias = dataCat.categorias;
        todasLasSubcategorias = dataCat.subcategorias;
    } catch (err) {
        return alert(err.message);
    }

    document.getElementById('fecha').value = fechaHoyISO();

    // Actualizar fecha en el header superior (Ej: 27 sep. 2026)
    const opcionesFecha = { day: 'numeric', month: 'short', year: 'numeric' };
    document.getElementById('fecha-header').innerText = new Date().toLocaleDateString('es-ES', opcionesFecha);

    cambiarTipo('Gasto'); // Iniciar por defecto en Gasto
    aplicarPrellenado();
    cargarSugerenciasPersonas();
    await refrescarCuentasYMovimientos();
}

// ---------- Gasto compartido ----------

// Sugerencias del campo "persona": usuarios de OptiFin (menos yo) y personas ya usadas en deudas
async function cargarSugerenciasPersonas() {
    let data;
    try {
        data = await api('/deudas/personas');
    } catch (err) {
        return; // Sin sugerencias igual se puede escribir el nombre a mano
    }
    const usuarios = data.usuarios.filter(u => u.id_usuario !== USUARIO_ACTUAL.id);
    document.getElementById('sugerencias_personas').innerHTML =
        usuarios.map(u => `<option value="${esc(u.nombre)}">Usuario de OptiFin</option>`).join('') +
        data.personas.map(p => `<option value="${esc(p)}"></option>`).join('');
}

function filasParticipantes() {
    return [...document.querySelectorAll('#lista_participantes .participante')];
}

function agregarParticipante(nombre = '', monto = '') {
    const fila = document.createElement('div');
    fila.className = 'participante flex gap-2';
    fila.innerHTML = `
        <input type="text" list="sugerencias_personas" placeholder="Nombre de la persona" class="p-nombre flex-1 min-w-0 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
        <input type="number" min="1" step="any" placeholder="Te debe $" class="p-monto w-32 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">
        <button type="button" class="p-quitar text-gray-400 hover:text-red-600 px-2 text-lg leading-none" title="Quitar">×</button>`;
    fila.querySelector('.p-nombre').value = nombre;
    fila.querySelector('.p-monto').value = monto;
    fila.querySelector('.p-monto').addEventListener('input', actualizarResumenCompartido);
    fila.querySelector('.p-quitar').addEventListener('click', () => {
        fila.remove();
        if (filasParticipantes().length === 0) agregarParticipante();
        actualizarResumenCompartido();
    });
    document.getElementById('lista_participantes').appendChild(fila);
    return fila;
}

function totalTeDeben() {
    return filasParticipantes().reduce((s, f) => s + (parseFloat(f.querySelector('.p-monto').value) || 0), 0);
}

function actualizarResumenCompartido() {
    const total = parseFloat(document.getElementById('monto').value) || 0;
    const teDeben = totalTeDeben();
    document.getElementById('resumen_te_deben').innerText = formatoMoneda(teDeben);
    const tuParte = document.getElementById('resumen_tu_parte');
    tuParte.innerText = formatoMoneda(total - teDeben);
    tuParte.classList.toggle('text-red-600', teDeben > total);
    tuParte.classList.toggle('text-gray-800', teDeben <= total);
}

// Divide el total entre los participantes y yo; el redondeo (pesos) queda en mi parte
function dividirEnPartesIguales() {
    const total = parseFloat(document.getElementById('monto').value) || 0;
    if (total <= 0) return alert("Primero escribe el monto total del gasto.");
    const filas = filasParticipantes();
    const parte = Math.floor(total / (filas.length + 1));
    filas.forEach(f => f.querySelector('.p-monto').value = parte);
    actualizarResumenCompartido();
}

function reiniciarCompartido() {
    document.getElementById('chk_compartido').checked = false;
    document.getElementById('panel_compartido').classList.add('hidden');
    document.getElementById('lista_participantes').innerHTML = '';
    actualizarResumenCompartido();
}

// Devuelve la lista de participantes para el backend, o lanza un Error si algo falta
function leerCompartido() {
    if (!document.getElementById('chk_compartido').checked) return [];
    const participantes = filasParticipantes()
        .map(f => ({ persona: f.querySelector('.p-nombre').value.trim(), monto: parseFloat(f.querySelector('.p-monto').value) }))
        .filter(p => p.persona || p.monto);  // Ignorar filas totalmente vacías
    if (participantes.length === 0) throw new Error("Agrega al menos una persona al gasto compartido, o desmarca la casilla.");
    if (participantes.some(p => !p.persona || !(p.monto > 0))) throw new Error("Cada persona del gasto compartido necesita nombre y un monto mayor a 0.");
    if (totalTeDeben() > parseFloat(document.getElementById('monto').value)) throw new Error("Lo que te deben no puede superar el total del gasto.");
    return participantes;
}

document.getElementById('chk_compartido').addEventListener('change', (e) => {
    document.getElementById('panel_compartido').classList.toggle('hidden', !e.target.checked);
    if (e.target.checked && filasParticipantes().length === 0) agregarParticipante().querySelector('.p-nombre').focus();
    actualizarResumenCompartido();
});
document.getElementById('btn_agregar_participante').addEventListener('click', () => agregarParticipante().querySelector('.p-nombre').focus());
document.getElementById('btn_dividir').addEventListener('click', dividirEnPartesIguales);
document.getElementById('monto').addEventListener('input', actualizarResumenCompartido);

// Permite abrir la página con el formulario lleno desde el Dashboard,
// p. ej. index.html?tipo=Gasto&sub=2&monto=1200000&desc=Arriendo&fecha=2026-09-27
function aplicarPrellenado() {
    const params = new URLSearchParams(window.location.search);
    const tipo = params.get('tipo');
    if (!['Gasto', 'Ingreso', 'Traslado'].includes(tipo)) return;

    const idSub = parseInt(params.get('sub'));
    const sub = todasLasSubcategorias.find(s => s.ID_Subcategoria === idSub);
    if (sub) categoriaSeleccionada = sub.ID_Categoria;
    cambiarTipo(tipo);
    if (sub) document.getElementById('id_subcategoria').value = idSub;

    if (params.get('monto')) document.getElementById('monto').value = params.get('monto');
    if (params.get('desc')) document.getElementById('descripcion').value = params.get('desc');
    if (/^\d{4}-\d{2}-\d{2}$/.test(params.get('fecha') || '')) document.getElementById('fecha').value = params.get('fecha');

    // Limpiar la URL para que recargar la página no vuelva a prellenar
    history.replaceState(null, '', window.location.pathname);
    document.getElementById('monto').focus();
}

// Recarga saldos y la tabla sin tocar lo que el usuario tiene elegido en el formulario
async function refrescarCuentasYMovimientos() {
    try {
        todasLasCuentas = await api(RUTA_CUENTAS);
    } catch (err) {
        return alert(err.message);
    }
    poblarCuentas();
    cargarTransacciones();
}

function poblarCuentas() {
    const opciones = todasLasCuentas.length === 0
        ? `<option value="">Sin cuentas (créalas en Cuentas)</option>`
        : todasLasCuentas.map(c => `<option value="${c.id_cuenta}">${esc(c.nombre)} (${formatoMoneda(c.saldo_actual)})</option>`).join('');

    // Conservar la cuenta que el usuario tenía elegida
    for (const id of ['id_cuenta_origen', 'id_cuenta_destino']) {
        const select = document.getElementById(id);
        const seleccionPrevia = select.value;
        select.innerHTML = opciones;
        if (todasLasCuentas.some(c => String(c.id_cuenta) === seleccionPrevia)) select.value = seleccionPrevia;
    }
}

// Controla el diseño de los 3 botones superiores
window.cambiarTipo = function(tipo) {
    document.getElementById('tipo').value = tipo;

    const btnGasto = document.getElementById('btn-gasto');
    const btnIngreso = document.getElementById('btn-ingreso');
    const btnTraslado = document.getElementById('btn-traslado');

    // Resetear estilos a inactivos
    const clsInactivo = ['border-transparent', 'text-gray-500', 'hover:bg-gray-50'];
    btnGasto.classList.remove('border-red-200', 'bg-red-50', 'text-red-600');
    btnGasto.classList.add(...clsInactivo);
    btnIngreso.classList.remove('border-green-200', 'bg-green-50', 'text-green-700');
    btnIngreso.classList.add(...clsInactivo);
    btnTraslado.classList.remove('border-blue-200', 'bg-blue-50', 'text-blue-700');
    btnTraslado.classList.add(...clsInactivo);

    const boxOrigen = document.getElementById('box_origen');
    const boxDestino = document.getElementById('box_destino');
    const panelCategorias = document.getElementById('panel_categorias');
    const boxCatSub = document.getElementById('box_categoria_sub');
    const lblOrigen = document.getElementById('lbl_origen');
    const selectSub = document.getElementById('id_subcategoria');

    // Solo un gasto puede ser compartido
    document.getElementById('box_compartido').classList.toggle('hidden', tipo !== 'Gasto');
    if (tipo !== 'Gasto') reiniciarCompartido();

    if (tipo === 'Gasto') {
        btnGasto.classList.remove(...clsInactivo);
        btnGasto.classList.add('border-red-200', 'bg-red-50', 'text-red-600');
        boxOrigen.classList.remove('hidden');
        boxDestino.classList.add('hidden');
        panelCategorias.classList.remove('hidden');
        boxCatSub.classList.remove('hidden');
        selectSub.required = true;
        lblOrigen.innerText = 'Cuenta de Origen';
        dibujarGridCategorias('Gasto');

    } else if (tipo === 'Ingreso') {
        btnIngreso.classList.remove(...clsInactivo);
        btnIngreso.classList.add('border-green-200', 'bg-green-50', 'text-green-700');
        boxOrigen.classList.add('hidden');
        boxDestino.classList.remove('hidden');
        panelCategorias.classList.remove('hidden');
        boxCatSub.classList.remove('hidden');
        selectSub.required = true;
        dibujarGridCategorias('Ingreso');

    } else if (tipo === 'Traslado') {
        btnTraslado.classList.remove(...clsInactivo);
        btnTraslado.classList.add('border-blue-200', 'bg-blue-50', 'text-blue-700');
        boxOrigen.classList.remove('hidden');
        boxDestino.classList.remove('hidden');
        panelCategorias.classList.add('hidden');
        boxCatSub.classList.add('hidden');
        selectSub.required = false; // Un select oculto y obligatorio bloquearía el envío del formulario
        lblOrigen.innerText = 'Sale de:';
    }

    // "¿Quién pagó?" solo aplica a gastos
    document.getElementById('box_quien_pago').classList.toggle('hidden', tipo !== 'Gasto');
    aplicarQuienPago();
}

// ---------- ¿Quién pagó? ----------

let pagoOtraPersona = false;

function aplicarQuienPago() {
    const esGasto = document.getElementById('tipo').value === 'Gasto';
    const otro = esGasto && pagoOtraPersona;

    for (const [id, activo] of [['btn_pague_yo', !pagoOtraPersona], ['btn_pago_otro', pagoOtraPersona]]) {
        const boton = document.getElementById(id);
        boton.classList.toggle('bg-white', activo);
        boton.classList.toggle('shadow-sm', activo);
        boton.classList.toggle('text-gray-800', activo);
        boton.classList.toggle('text-gray-500', !activo);
    }
    document.getElementById('box_pagado_por').classList.toggle('hidden', !otro);
    document.getElementById('lbl_monto').innerText = otro ? 'Tu parte' : 'Monto';

    if (esGasto) {
        // Si lo pagó otra persona no sale de mis cuentas ni puede ser además compartido
        document.getElementById('box_origen').classList.toggle('hidden', otro);
        document.getElementById('box_compartido').classList.toggle('hidden', otro);
        if (otro) reiniciarCompartido();
    }
}

function cambiarQuienPago(otro) {
    pagoOtraPersona = otro;
    aplicarQuienPago();
    if (otro) document.getElementById('pagado_por').focus();
}

document.getElementById('btn_pague_yo').addEventListener('click', () => cambiarQuienPago(false));
document.getElementById('btn_pago_otro').addEventListener('click', () => cambiarQuienPago(true));

function dibujarGridCategorias(tipoMovimiento) {
    const grid = document.getElementById('grid-categorias');
    const catsFiltradas = todasLasCategorias.filter(c => c.Tipo_Movimiento === tipoMovimiento);

    // Si no hay categoría seleccionada, seleccionar la primera por defecto
    if (!catsFiltradas.find(c => c.ID_Categoria === categoriaSeleccionada)) {
        categoriaSeleccionada = catsFiltradas.length > 0 ? catsFiltradas[0].ID_Categoria : null;
    }

    if (catsFiltradas.length === 0) {
        grid.innerHTML = `<p class="col-span-3 text-sm text-gray-400 italic">No hay categorías de ${tipoMovimiento.toLowerCase()}. Créalas en Categorías.</p>`;
    } else {
        // Colores para que se vea parecido a la imagen (solo estética)
        const bgIconos = ['bg-blue-100 text-blue-600', 'bg-orange-100 text-orange-600', 'bg-indigo-100 text-indigo-600', 'bg-green-100 text-green-600', 'bg-purple-100 text-purple-600', 'bg-pink-100 text-pink-600'];

        grid.innerHTML = catsFiltradas.map((c, index) => {
            const esActiva = categoriaSeleccionada === c.ID_Categoria;
            const colorClase = bgIconos[index % bgIconos.length];
            const claseActiva = esActiva ? 'border-blue-500 bg-blue-50/50 shadow-sm' : 'border-gray-100 hover:border-gray-300 bg-white';

            return `
            <div onclick="seleccionarCategoriaGrilla(${c.ID_Categoria})" class="cursor-pointer border-2 rounded-2xl p-4 flex flex-col items-center justify-center gap-2 transition-all duration-200 ${claseActiva}">
                <div class="w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg ${colorClase}">
                    ${esc(String(c.Nombre_Categoria).charAt(0))}
                </div>
                <span class="text-xs text-center font-semibold ${esActiva ? 'text-blue-700' : 'text-gray-600'}">${esc(c.Nombre_Categoria)}</span>
            </div>`;
        }).join('');
    }

    document.getElementById('id_categoria').value = categoriaSeleccionada ?? '';
    filtrarSubcategorias();
}

window.seleccionarCategoriaGrilla = function(idCategoria) {
    categoriaSeleccionada = idCategoria;
    dibujarGridCategorias(document.getElementById('tipo').value); // Redibujar para actualizar el borde azul
}

function filtrarSubcategorias() {
    const selectSub = document.getElementById('id_subcategoria');
    const subsFiltradas = todasLasSubcategorias.filter(s => s.ID_Categoria === categoriaSeleccionada);

    selectSub.innerHTML = subsFiltradas.length === 0
        ? `<option value="">Sin conceptos creados</option>`
        : subsFiltradas.map(sub => `<option value="${sub.ID_Subcategoria}">${esc(sub.Nombre_Subcategoria)}</option>`).join('');
}

// ---------- Cuenta de cada movimiento (etiqueta visual) ----------

// Cada cuenta conserva siempre el mismo color (según su orden de creación), y un ícono según su tipo
const COLORES_CUENTA = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
const ICONOS_CUENTA = {
    'Crédito': 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z',
    'Efectivo': 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z',
    'Billetera Digital': 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z',
    'Débito': 'M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z',
};

function chipCuenta(id) {
    const orden = [...todasLasCuentas].sort((a, b) => a.id_cuenta - b.id_cuenta);
    const i = orden.findIndex(c => c.id_cuenta === id);
    if (i < 0) return '<span class="text-xs text-gray-400">Cuenta eliminada</span>';
    const c = orden[i];
    const icono = ICONOS_CUENTA[c.tipo] || ICONOS_CUENTA['Débito'];
    return `<span class="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold text-gray-700 bg-gray-100 rounded-full pl-1.5 pr-2.5 py-1" title="${esc(c.tipo)}">
        <span class="inline-flex items-center justify-center w-5 h-5 rounded-full text-white shrink-0" style="background:${COLORES_CUENTA[i % COLORES_CUENTA.length]}">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${icono}"></path></svg>
        </span>${esc(c.nombre)}</span>`;
}

// De qué cuenta salió (gasto), a cuál entró (ingreso) o ambas (traslado)
function celdaCuenta(t) {
    if (t.Compartido_Por) return `<span class="text-xs text-gray-400">Lo pagó ${esc(t.Compartido_Por)}</span>`;
    if (t.Pagado_Por) return `<span class="text-xs text-gray-400">Lo pagó ${esc(t.Pagado_Por)}</span>`;
    const flecha = '<span class="text-gray-400 mx-1">→</span>';
    if (t.Tipo_Movimiento === 'Traslado') return `<span class="inline-flex items-center flex-wrap gap-y-1">${chipCuenta(t.ID_Cuenta_Origen)}${flecha}${chipCuenta(t.ID_Cuenta_Destino)}</span>`;
    if (t.Tipo_Movimiento === 'Ingreso') return t.ID_Cuenta_Destino ? `<span class="inline-flex items-center">${flecha}${chipCuenta(t.ID_Cuenta_Destino)}</span>` : '-';
    return t.ID_Cuenta_Origen ? chipCuenta(t.ID_Cuenta_Origen) : '-';
}

// ---------- Lista de movimientos (paginada de 10 en 10) ----------

const TAMANO_PAGINA = 10;
let movimientosCargados = [];
let hayMasMovimientos = false;
let idEditando = null;

// reiniciar=true vuelve a la primera página (tras guardar, editar o anular); false agrega la siguiente
async function cargarTransacciones(reiniciar = true) {
    const desde = reiniciar ? 0 : movimientosCargados.length;
    // Al recargar se conserva cuántos había a la vista (si el usuario ya había pedido "ver más")
    const limite = reiniciar ? Math.max(TAMANO_PAGINA, movimientosCargados.length) : TAMANO_PAGINA;
    let datos;
    try {
        datos = await api(`${RUTA_TRANS}?desde=${desde}&limite=${limite}`);
    } catch (err) {
        return alert(err.message);
    }
    movimientosCargados = reiniciar ? datos.movimientos : movimientosCargados.concat(datos.movimientos);
    hayMasMovimientos = datos.hay_mas;
    dibujarMovimientos();
}

function dibujarMovimientos() {
    document.getElementById('btn_ver_mas').classList.toggle('hidden', !hayMasMovimientos);
    const tbody = document.getElementById('tablaResultados');
    if (movimientosCargados.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="py-6 text-center text-gray-400 italic">Aún no hay movimientos.</td></tr>';
        return;
    }

    tbody.innerHTML = movimientosCargados.map(t => {
        let badge = `<span class="bg-blue-100 text-blue-700 py-1 px-3 rounded-md text-xs font-bold">Traslado</span>`;
        if (t.Tipo_Movimiento === 'Ingreso') badge = `<span class="bg-green-100 text-green-700 py-1 px-3 rounded-md text-xs font-bold">Ingreso</span>`;
        if (t.Tipo_Movimiento === 'Gasto') badge = `<span class="bg-red-100 text-red-700 py-1 px-3 rounded-md text-xs font-bold">Gasto</span>`;
        if (t.Anulada) badge = `<span class="bg-gray-200 text-gray-600 py-1 px-3 rounded-md text-xs font-bold">Anulado</span>`;

        // Concepto: subcategoría para gastos/ingresos, cuentas para traslados
        let concepto = "-";
        if (t.Tipo_Movimiento === 'Traslado') {
            concepto = "Traslado entre cuentas";
        } else if (t.ID_Subcategoria) {
            const sub = todasLasSubcategorias.find(s => s.ID_Subcategoria === t.ID_Subcategoria);
            concepto = sub ? sub.Nombre_Subcategoria : "Desconocido";
        }

        let acciones;
        if (t.Solo_Lectura) {
            acciones = '<span class="text-xs text-gray-400" title="Lo registró la otra persona; si hay un error, debe corregirlo ella">Solo lectura</span>';
        } else if (t.Anulada) {
            acciones = `<button type="button" onclick="restaurarTransaccion(${t.ID_Transaccion})" class="text-blue-600 hover:text-blue-800 text-xs font-bold">Restaurar</button>`;
        } else {
            acciones = `<button type="button" onclick="editarTransaccion(${t.ID_Transaccion})" class="text-blue-600 hover:text-blue-800 text-xs font-bold">Editar</button>
                        <button type="button" onclick="anularTransaccion(${t.ID_Transaccion})" class="text-red-500 hover:text-red-700 text-xs font-bold ml-3">Anular</button>`;
        }
        const tachado = t.Anulada ? 'line-through text-gray-400' : '';

        return `
        <tr class="border-b border-gray-100 hover:bg-gray-50/50 transition-colors ${t.Anulada ? 'bg-gray-50' : ''} ${t.ID_Transaccion === idEditando ? 'ring-2 ring-amber-300' : ''}">
            <td class="py-4 px-4 text-left whitespace-nowrap ${tachado}">${esc(String(t.Fecha ?? '').slice(0, 10))}</td>
            <td class="py-4 px-4 text-left">${badge}</td>
            <td class="py-4 px-4 text-left ${t.Anulada ? 'opacity-50' : ''}">${celdaCuenta(t)}</td>
            <td class="py-4 px-4 text-left text-gray-600 ${tachado}">${esc(concepto)}</td>
            <td class="py-4 px-4 text-right font-bold text-gray-800">
                <span class="${tachado}">${formatoMoneda(t.Monto)}</span>
                ${t.Monto_Compartido > 0 ? `<span class="block text-xs font-normal text-gray-400">Compartido · tu parte ${formatoMoneda(t.Monto - t.Monto_Compartido)}</span>` : ''}
                ${t.Pagado_Por ? `<span class="block text-xs font-normal text-gray-400">Lo pagó ${esc(t.Pagado_Por)} · le debes</span>` : ''}
                ${t.Compartido_Por ? `<span class="block text-xs font-normal text-gray-400">Lo pagó ${esc(t.Compartido_Por)} y lo compartió contigo · tu parte</span>` : ''}
            </td>
            <td class="py-4 px-4 text-left text-gray-500 text-sm truncate max-w-[200px] ${tachado}">${esc(t.Descripcion)}</td>
            <td class="py-4 px-4 text-right whitespace-nowrap">${acciones}</td>
        </tr>`;
    }).join('');
}

document.getElementById('btn_ver_mas').addEventListener('click', () => cargarTransacciones(false));

window.anularTransaccion = async function(id) {
    const t = movimientosCargados.find(m => m.ID_Transaccion === id);
    const aviso = "¿Anular este movimiento? Seguirá visible (tachado) pero dejará de contar en tus saldos y resúmenes." +
        (t && t.Monto_Compartido > 0 ? "\nComo es un gasto compartido, también se anularán las deudas que generó." : "") +
        "\nPuedes restaurarlo después.";
    if (!confirm(aviso)) return;
    try {
        await api(`${RUTA_TRANS}${id}/anular`, { method: "POST" });
        if (idEditando === id) salirDeEdicion();
        refrescarCuentasYMovimientos();
    } catch (err) {
        alert(err.message);
    }
}

window.restaurarTransaccion = async function(id) {
    try {
        await api(`${RUTA_TRANS}${id}/restaurar`, { method: "POST" });
        refrescarCuentasYMovimientos();
    } catch (err) {
        alert(err.message);
    }
}

// ---------- Edición ----------

window.editarTransaccion = function(id) {
    const t = movimientosCargados.find(m => m.ID_Transaccion === id);
    if (!t) return;
    if (t.Pagado_Por) {
        return alert(`Este gasto lo pagó ${t.Pagado_Por}: para cambiarlo, anúlalo y regístralo de nuevo.`);
    }
    idEditando = id;

    // Tipo, categoría y subcategoría
    const sub = todasLasSubcategorias.find(s => s.ID_Subcategoria === t.ID_Subcategoria);
    if (sub) categoriaSeleccionada = sub.ID_Categoria;
    cambiarQuienPago(false);
    cambiarTipo(t.Tipo_Movimiento);
    if (sub) document.getElementById('id_subcategoria').value = t.ID_Subcategoria;

    // Cuentas, monto, nota y fecha
    if (t.ID_Cuenta_Origen) document.getElementById('id_cuenta_origen').value = t.ID_Cuenta_Origen;
    if (t.ID_Cuenta_Destino) document.getElementById('id_cuenta_destino').value = t.ID_Cuenta_Destino;
    document.getElementById('monto').value = t.Monto;
    document.getElementById('descripcion').value = t.Descripcion || '';
    document.getElementById('fecha').value = String(t.Fecha).slice(0, 10);

    // En edición no se cambia quién pagó ni con quién se comparte (las partes se ajustan en Deudas)
    document.getElementById('box_quien_pago').classList.add('hidden');
    document.getElementById('box_compartido').classList.add('hidden');
    reiniciarCompartido();

    document.getElementById('titulo_form_mov').innerText = 'Editar Movimiento';
    document.getElementById('texto_btn_guardar').innerText = 'Guardar cambios';
    document.getElementById('aviso_edicion_texto').innerText = t.Monto_Compartido > 0
        ? `Editando un gasto compartido: el monto no puede ser menor a lo que te deben (${formatoMoneda(t.Monto_Compartido)}).`
        : 'Estás editando un movimiento.';
    document.getElementById('aviso_edicion').classList.remove('hidden');
    dibujarMovimientos();
    document.getElementById('transaccionForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function salirDeEdicion() {
    idEditando = null;
    document.getElementById('titulo_form_mov').innerText = 'Nuevo Movimiento';
    document.getElementById('texto_btn_guardar').innerText = 'Registrar Movimiento';
    document.getElementById('aviso_edicion').classList.add('hidden');
    document.getElementById('monto').value = '';
    document.getElementById('descripcion').value = '';
    document.getElementById('fecha').value = fechaHoyISO();
    cambiarTipo(document.getElementById('tipo').value);  // vuelve a mostrar "¿Quién pagó?" y el compartido
    dibujarMovimientos();
}

document.getElementById('btn_cancelar_edicion').addEventListener('click', salirDeEdicion);

document.getElementById('transaccionForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const tipo = document.getElementById('tipo').value;
    const pagadoPor = idEditando === null && tipo === 'Gasto' && pagoOtraPersona ? document.getElementById('pagado_por').value.trim() : null;
    if (tipo === 'Gasto' && pagoOtraPersona && !pagadoPor) return alert("Escribe quién pagó el gasto.");
    // Un gasto que pagó otra persona no usa cuentas
    if (!pagadoPor && todasLasCuentas.length === 0) return alert("Primero crea al menos una cuenta en la sección Cuentas.");

    let id_origen = null;
    let id_destino = null;
    let id_sub = null;

    if (tipo === 'Gasto') {
        if (!pagadoPor) id_origen = parseInt(document.getElementById('id_cuenta_origen').value);
        id_sub = parseInt(document.getElementById('id_subcategoria').value);
    } else if (tipo === 'Ingreso') {
        id_destino = parseInt(document.getElementById('id_cuenta_destino').value);
        id_sub = parseInt(document.getElementById('id_subcategoria').value);
    } else if (tipo === 'Traslado') {
        id_origen = parseInt(document.getElementById('id_cuenta_origen').value);
        id_destino = parseInt(document.getElementById('id_cuenta_destino').value);
        if (id_origen === id_destino) return alert("No puedes trasladar dinero a la misma cuenta.");
    }

    if ((tipo === 'Gasto' || tipo === 'Ingreso') && isNaN(id_sub)) {
        return alert("Debes crear al menos una subcategoría (concepto) en el menú Categorías para poder registrar el movimiento.");
    }

    let compartido;
    try {
        compartido = idEditando === null && tipo === 'Gasto' && !pagadoPor ? leerCompartido() : [];
    } catch (err) {
        return alert(err.message);
    }

    const t = {
        fecha: document.getElementById('fecha').value,
        tipo_movimiento: tipo,
        id_subcategoria: isNaN(id_sub) ? null : id_sub,
        id_cuenta_origen: isNaN(id_origen) ? null : id_origen,
        id_cuenta_destino: isNaN(id_destino) ? null : id_destino,
        monto: parseFloat(document.getElementById('monto').value),
        descripcion: document.getElementById('descripcion').value,
        compartido: compartido,
        pagado_por: pagadoPor
    };

    try {
        if (idEditando !== null) {
            await api(`${RUTA_TRANS}${idEditando}`, { method: "PUT", body: { ...t, compartido: [], pagado_por: null } });
            salirDeEdicion();
            return refrescarCuentasYMovimientos();
        }
        await api(RUTA_TRANS, { method: "POST", body: t });
    } catch (err) {
        return alert(err.message);
    }
    if (pagadoPor) cargarSugerenciasPersonas(); // Incluir a la persona si es nueva

    // Limpiar solo monto, nota y compartido: tipo, cuentas, categoría y fecha se conservan para registrar varios seguidos
    document.getElementById('monto').value = '';
    document.getElementById('descripcion').value = '';
    if (compartido.length > 0) cargarSugerenciasPersonas(); // Incluir las personas nuevas
    reiniciarCompartido();
    refrescarCuentasYMovimientos();
});

// Arrancar App
cargarConfiguracion();
