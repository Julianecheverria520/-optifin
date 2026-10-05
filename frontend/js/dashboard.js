const RUTA_DASHBOARD = "/dashboard/resumen/";

// Etiqueta y color de cada estado de un fijo; "pagado" se dice distinto para ingresos
const ESTADOS_FIJO = {
    pagado:    { gasto: "Pagado", ingreso: "Recibido", clase: "bg-green-100 text-green-800" },
    parcial:   { gasto: "Parcial", ingreso: "Parcial", clase: "bg-yellow-100 text-yellow-800" },
    pendiente: { gasto: "Pendiente", ingreso: "Pendiente", clase: "bg-gray-100 text-gray-700" },
    vencido:   { gasto: "Vencido", ingreso: "Atrasado", clase: "bg-red-100 text-red-800" },
};

function establecerMesActual() {
    const fecha = new Date();
    const anioActual = fecha.getFullYear();

    // Años disponibles: 3 hacia atrás y 1 hacia adelante del año en curso
    const selectAnio = document.getElementById('anioSelect');
    const anios = [];
    for (let a = anioActual - 3; a <= anioActual + 1; a++) anios.push(a);
    selectAnio.innerHTML = anios.map(a => `<option value="${a}">${a}</option>`).join('');

    document.getElementById('mesSelect').value = fecha.getMonth() + 1;
    selectAnio.value = anioActual;
}

function ponerMonto(id, valor, colorPorSigno = false) {
    const el = document.getElementById(id);
    el.innerText = formatoMoneda(valor);
    if (colorPorSigno) {
        el.classList.toggle('text-red-600', valor < 0);
        el.classList.toggle('text-gray-800', valor >= 0);
    }
}

// ---------- Ajuste del valor de un concepto solo para el mes elegido ----------

function editorAjuste(id, valorActual, ajustado, etiqueta) {
    return `
        <div id="editor_${id}" class="hidden mt-2 flex flex-wrap items-center gap-2">
            <input type="number" min="1" step="any" value="${valorActual}" class="aj-monto w-36 px-2 py-1 border border-gray-300 rounded text-sm">
            <button type="button" onclick="guardarAjuste(${id})" class="text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded">Guardar</button>
            ${ajustado ? `<button type="button" onclick="quitarAjuste(${id})" class="text-xs font-bold text-gray-700 bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded">Volver al plan</button>` : ''}
            <button type="button" onclick="alternarEditor(${id})" class="text-xs text-gray-500 hover:text-gray-700">Cancelar</button>
            <span class="text-xs text-gray-400">${etiqueta} solo para este mes; la planificación no cambia.</span>
        </div>`;
}

window.alternarEditor = function(id) {
    const editor = document.getElementById(`editor_${id}`);
    editor.classList.toggle('hidden');
    if (!editor.classList.contains('hidden')) editor.querySelector('.aj-monto').select();
}

function rutaAjuste(id) {
    const mes = document.getElementById('mesSelect').value;
    const anio = document.getElementById('anioSelect').value;
    return `/planificacion/${id}/ajuste/${anio}/${mes}`;
}

window.guardarAjuste = async function(id, montoFijo) {
    const monto = montoFijo ?? parseFloat(document.querySelector(`#editor_${id} .aj-monto`).value);
    if (!(monto > 0)) return alert("Escribe un valor mayor a 0.");
    try {
        await api(rutaAjuste(id), { method: "PUT", body: { monto } });
        cargarDashboard();
    } catch (err) {
        alert(err.message);
    }
}

window.quitarAjuste = async function(id) {
    try {
        await api(rutaAjuste(id), { method: "DELETE" });
        cargarDashboard();
    } catch (err) {
        alert(err.message);
    }
}

// Texto del desvío contra la plantilla: "$5.000 más de lo planeado"
function textoDesvio(diferencia) {
    return `${formatoMoneda(Math.abs(diferencia))} ${diferencia > 0 ? 'más' : 'menos'} de lo planeado`;
}

// De entrada solo se ven los fijos pendientes; los ya pagados/recibidos se muestran con un botón
let fijosDelMes = [];
let verFijosPagados = false;

window.alternarFijosPagados = function() {
    verFijosPagados = !verFijosPagados;
    dibujarFijos(fijosDelMes);
};

function dibujarFijos(fijos) {
    fijosDelMes = fijos;
    const cont = document.getElementById('contenedor_fijos');
    const boton = document.getElementById('btn_fijos_pagados');
    const pagados = fijos.filter(f => f.estado === 'pagado').length;
    boton.classList.toggle('hidden', pagados === 0);
    boton.innerText = verFijosPagados ? 'Ver solo pendientes' : `Ver todos (${pagados} ${pagados === 1 ? 'pagado' : 'pagados'})`;

    if (fijos.length === 0) {
        cont.innerHTML = '<p class="text-gray-500 text-sm italic">No hay ingresos ni gastos fijos activos. Créalos en la sección Presupuesto.</p>';
        return;
    }
    const visibles = verFijosPagados ? fijos : fijos.filter(f => f.estado !== 'pagado');
    if (visibles.length === 0) {
        cont.innerHTML = '<p class="text-green-700 text-sm font-semibold py-2">Todo al día: no tienes pagos ni cobros fijos pendientes este mes.</p>';
        return;
    }

    cont.innerHTML = visibles.map(f => {
        const esIngreso = f.tipo_movimiento === 'Ingreso';
        const estado = ESTADOS_FIJO[f.estado];
        const etiqueta = esIngreso ? estado.ingreso : estado.gasto;
        const pagado = f.estado === 'pagado';
        const detalle = f.estado === 'parcial' || (f.estado === 'vencido' && f.cubierto > 0)
            ? `<span class="text-xs text-gray-400">(${formatoMoneda(f.cubierto)} de ${formatoMoneda(f.monto)})</span>` : '';
        const notaAjuste = f.ajustado
            ? `<span class="text-xs text-gray-400 font-normal">(ajustado este mes · plan ${formatoMoneda(f.monto_plan)})</span>` : '';

        // Desvío contra lo planeado: al pagar, con lo pagado; antes, con el valor ajustado
        let desvio = '';
        if (Math.abs(f.diferencia_plan) >= 1) {
            // Para un gasto, pagar más es malo (rojo); para un ingreso, recibir más es bueno (verde)
            const malo = esIngreso ? f.diferencia_plan < 0 : f.diferencia_plan > 0;
            const inicio = pagado ? `${esIngreso ? 'Recibiste' : 'Pagaste'} ${formatoMoneda(f.pagado)} · ` : '';
            desvio = `<p class="text-xs font-semibold ${malo ? 'text-red-600' : 'text-green-700'}">${inicio}${textoDesvio(f.diferencia_plan)}</p>`;
        }

        // Pago parcial: puede que la factura haya llegado por menos. Un clic la ajusta a lo pagado y queda saldada
        const llegoPorMenos = !pagado && f.cubierto > 0
            ? `<button type="button" onclick="guardarAjuste(${f.id_registro}, ${f.cubierto})" class="mt-1 text-xs font-semibold text-green-700 hover:text-green-900 underline">¿${esIngreso ? 'Llegó' : 'La factura llegó'} por ${formatoMoneda(f.cubierto)}? Marcar como ${esIngreso ? 'recibido' : 'pagado'}</button>`
            : '';

        const botones = pagado ? '' : `
            <button type="button" onclick="alternarEditor(${f.id_registro})" class="text-xs font-bold text-gray-600 hover:text-gray-800 bg-gray-100 px-2 py-1 rounded">Ajustar</button>
            <a href="${enlaceRegistrarFijo(f)}" class="text-xs font-bold text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-1 rounded">${esIngreso ? 'Registrar cobro' : 'Registrar pago'}</a>`;

        return `
            <div class="py-3">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="min-w-0">
                        <p class="font-medium text-gray-800 truncate">${esc(f.concepto)} <span class="text-xs text-gray-400 font-normal">${f.dia_mes ? `día ${f.dia_mes}` : 'sin día fijo'}</span></p>
                        <p class="text-sm ${esIngreso ? 'text-green-700' : 'text-red-600'} font-semibold">${esIngreso ? '+' : '-'}${formatoMoneda(f.monto)} ${notaAjuste} ${detalle}</p>
                        ${desvio}
                        ${llegoPorMenos}
                    </div>
                    <div class="flex items-center gap-2 shrink-0">
                        <span class="text-xs font-bold px-2 py-1 rounded ${estado.clase}">${etiqueta}</span>
                        ${botones}
                    </div>
                </div>
                ${pagado ? '' : editorAjuste(f.id_registro, f.monto, f.ajustado, esIngreso ? 'Valor esperado' : 'Valor de la factura')}
            </div>`;
    }).join('');
}

function dibujarPresupuestos(presupuestos) {
    const contenedor = document.getElementById('contenedor_presupuestos');
    if (presupuestos.length === 0) {
        contenedor.innerHTML = '<p class="text-gray-500 text-sm italic">No hay presupuestos definidos. Créalos en la sección Presupuesto como "Tope Presupuestal".</p>';
        return;
    }

    // Barra de avance de un periodo (el mes completo o una quincena)
    const barra = (x, etiqueta) => {
        let colorBarra = "bg-green-500";
        if (x.porcentaje >= 70 && x.porcentaje < 90) colorBarra = "bg-yellow-400";
        if (x.porcentaje >= 90) colorBarra = "bg-red-500";
        const pie = x.excedido
            ? `<span class="font-bold text-red-600">Excedido por ${formatoMoneda(-x.restante)} (${x.porcentaje}%)</span>`
            : `<span class="text-gray-400">Quedan ${formatoMoneda(x.restante)} (${x.porcentaje}% usado)</span>`;
        return `
            <div class="${etiqueta ? 'mt-2' : ''}">
                ${etiqueta ? `<div class="flex justify-between text-xs text-gray-600 mb-0.5"><span>${etiqueta}${x.cerrado ? ' · cerrada' : ''}</span><span>${formatoMoneda(x.gastado)} / ${formatoMoneda(x.tope)}</span></div>` : ''}
                <div class="w-full bg-gray-200 rounded-full h-2.5 ${x.cerrado ? 'opacity-60' : ''}">
                    <div class="${colorBarra} h-2.5 rounded-full transition-all duration-500" style="width: ${Math.min(x.porcentaje, 100)}%"></div>
                </div>
                <p class="text-xs mt-1">${pie}</p>
            </div>`;
    };

    contenedor.innerHTML = presupuestos.map(p => {
        const quincenal = Array.isArray(p.quincenas);
        const notaAjuste = p.ajustado
            ? ` <span class="text-xs text-gray-400 font-normal">(tope ajustado este mes · plan ${formatoMoneda(p.tope_plan)}${quincenal ? ' por quincena' : ''})</span>` : '';
        const barras = quincenal
            ? p.quincenas.map(q => barra(q, `Quincena ${q.numero} (días ${q.rango})`)).join('')
            : barra(p, null);

        return `
            <div>
                <div class="flex justify-between text-sm font-medium text-gray-700 mb-1">
                    <span>${esc(p.concepto)} <span class="text-gray-400 font-normal">(${esc(p.subcategoria)}${quincenal ? ' · por quincena' : ''})</span>${notaAjuste}</span>
                    <span>${formatoMoneda(p.gastado)} / ${formatoMoneda(p.tope)}</span>
                </div>
                ${barras}
                <div class="flex justify-end">
                    <button type="button" onclick="alternarEditor(${p.id_registro})" class="text-xs text-gray-500 hover:text-gray-700">Ajustar tope</button>
                </div>
                ${editorAjuste(p.id_registro, p.valor_periodo, p.ajustado, quincenal ? 'Tope por quincena' : 'Tope')}
            </div>
        `;
    }).join('');
}

function dibujarDeudasPorPersona(personas, patrimonio) {
    ponerMonto('deu_me_deben', patrimonio.me_deben);
    ponerMonto('deu_debo', patrimonio.debo);

    const cont = document.getElementById('contenedor_personas');
    if (personas.length === 0) {
        cont.innerHTML = '<p class="text-gray-500 text-sm italic">Nadie te debe y no le debes a nadie.</p>';
        return;
    }

    cont.innerHTML = personas.map(p => {
        const meDebe = p.neto >= 0;
        // Si hay deudas en ambos sentidos con la misma persona, se muestra el desglose
        const desglose = p.me_debe > 0 && p.le_debo > 0
            ? `<span class="block text-xs text-gray-400">Neto de: te debe ${formatoMoneda(p.me_debe)}, le debes ${formatoMoneda(p.le_debo)}</span>` : '';
        return `
            <div class="py-3 flex flex-wrap items-center justify-between gap-3">
                <div class="min-w-0">
                    <p class="font-medium text-gray-800 truncate">
                        ${esc(p.persona)}
                        ${p.es_usuario ? '<span class="ml-1 text-[10px] font-bold uppercase bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Usuario OptiFin</span>' : ''}
                    </p>
                    <p class="text-xs text-gray-400">${p.deudas} ${p.deudas === 1 ? 'deuda pendiente' : 'deudas pendientes'}</p>
                </div>
                <div class="flex items-center gap-3 shrink-0 text-right">
                    <div>
                        <p class="text-sm font-bold ${meDebe ? 'text-green-700' : 'text-red-600'}">${meDebe ? 'Te debe' : 'Le debes'} ${formatoMoneda(Math.abs(p.neto))}</p>
                        ${desglose}
                    </div>
                    ${p.me_debe > 0 && p.le_debo > 0 ? `<a href="deudas.html?persona=${encodeURIComponent(p.persona)}&cruce=1" class="text-xs font-bold text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-1 rounded">Cruzar cuentas</a>` : ''}
                    <a href="deudas.html?persona=${encodeURIComponent(p.persona)}" class="text-xs font-bold text-purple-600 hover:text-purple-800 bg-purple-50 px-2 py-1 rounded">Ver detalle</a>
                </div>
            </div>`;
    }).join('');
}

async function cargarDashboard() {
    const mes = document.getElementById('mesSelect').value;
    const anio = document.getElementById('anioSelect').value;

    let data;
    try {
        data = await api(`${RUTA_DASHBOARD}${mes}/${anio}`);
    } catch (err) {
        return alert(err.message);
    }

    ponerMonto('total_ingresos', data.totales.ingresos);
    ponerMonto('total_gastos', data.totales.gastos);
    ponerMonto('total_saldo', data.totales.saldo, true);

    // En gastos compartidos solo cuenta tu parte; lo que pagaste por otros es un préstamo
    const porOtros = document.getElementById('total_por_otros');
    porOtros.classList.toggle('hidden', !(data.totales.pagado_por_otros > 0));
    porOtros.innerText = `Solo tu parte. Además pagaste ${formatoMoneda(data.totales.pagado_por_otros)} por otros (te lo deben)`;

    const p = data.proyeccion;
    ponerMonto('proy_ingresos', p.ingresos_plan);
    ponerMonto('proy_gastos_fijos', p.gastos_fijos_plan);
    ponerMonto('proy_presupuestos', p.presupuestos_plan);
    ponerMonto('proy_disponible', p.disponible_plan, true);
    if (p.es_mes_actual) {
        // Mes en curso: se parte del dinero real en cuentas (incluye saldos iniciales), no solo del historial del mes
        document.getElementById('proy_saldo_label').innerText = 'Si se cumple lo planeado, al final del mes tendrás en tus cuentas';
        ponerMonto('proy_saldo', p.saldo_fin_mes, true);
        document.getElementById('proy_saldo_nota').innerText =
            `Hoy tienes ${formatoMoneda(p.disponible_hoy)} (sin tarjetas de crédito) + lo que falta por recibir − lo que falta por pagar − el presupuesto que te queda.`;
    } else {
        // Otros meses: balance del mes según movimientos y plan
        document.getElementById('proy_saldo_label').innerText = 'Balance del mes si se cumple lo planeado';
        ponerMonto('proy_saldo', p.saldo_proyectado, true);
        document.getElementById('proy_saldo_nota').innerText =
            'Ingresos menos gastos del mes (registrados + pendientes según el plan).';
    }
    ponerMonto('proy_por_recibir', p.por_recibir);
    ponerMonto('proy_por_pagar', p.por_pagar);
    ponerMonto('proy_ppto_restante', p.presupuesto_restante);

    // Desvío de los fijos contra la planificación (facturas que llegaron por más/menos, etc.)
    const mostrarDesvio = (id, etiqueta, diferencia, esMalo) => {
        const el = document.getElementById(id);
        el.classList.toggle('hidden', Math.abs(diferencia) < 1);
        el.classList.toggle('text-red-600', esMalo);
        el.classList.toggle('text-green-700', !esMalo);
        el.innerText = `${etiqueta}: ${textoDesvio(diferencia)}`;
    };
    mostrarDesvio('proy_desvio_gastos', 'Gastos fijos', p.desvio_gastos_fijos, p.desvio_gastos_fijos > 0);
    mostrarDesvio('proy_desvio_ingresos', 'Ingresos fijos', p.desvio_ingresos_fijos, p.desvio_ingresos_fijos < 0);

    const pat = data.patrimonio;
    ponerMonto('pat_cuentas', pat.en_cuentas);
    ponerMonto('pat_tarjetas', pat.deuda_tarjetas);
    ponerMonto('pat_me_deben', pat.me_deben);
    ponerMonto('pat_debo', pat.debo);
    ponerMonto('pat_neto', pat.neto, true);

    dibujarFijos(data.fijos);
    dibujarPresupuestos(data.presupuestos);
    dibujarDeudasPorPersona(data.deudas_por_persona, pat);
}

establecerMesActual();
cargarDashboard();
