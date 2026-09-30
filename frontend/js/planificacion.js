const RUTA_PLAN = "/planificacion/";
const RUTA_CAT = "/categorias/";

let modoEdicion = false;
let idRegistroEditando = null;
let registrosPlan = []; // Última lista cargada, para buscar el registro a editar por ID
let categorias = [];
let subcategorias = [];

// Ingreso Fijo usa subcategorías de categorías de Ingreso; los demás, de Gasto
function tipoMovimientoDelPlan(tipoPlan) {
    return tipoPlan === "Ingreso Fijo" ? "Ingreso" : "Gasto";
}

// Selector de categoría según el tipo (Ingreso Fijo -> categorías de ingreso; el resto -> de gasto)
function poblarCategorias() {
    const tipoMov = tipoMovimientoDelPlan(document.getElementById('tipo_plan').value);
    const catsFiltradas = categorias.filter(c => c.Tipo_Movimiento === tipoMov);

    const select = document.getElementById('id_cat_plan');
    const seleccionPrevia = select.value;
    select.innerHTML = catsFiltradas.length === 0
        ? `<option value="">Sin categorías de ${tipoMov.toLowerCase()}</option>`
        : catsFiltradas.map(c => `<option value="${c.ID_Categoria}">${esc(c.Nombre_Categoria)}</option>`).join('');
    if (catsFiltradas.some(c => String(c.ID_Categoria) === seleccionPrevia)) select.value = seleccionPrevia;
    poblarSubcategorias();
}

// Selector de subcategoría anidado: solo las de la categoría elegida
function poblarSubcategorias() {
    const idCat = parseInt(document.getElementById('id_cat_plan').value);
    const subsFiltradas = subcategorias.filter(s => s.ID_Categoria === idCat);

    const select = document.getElementById('id_subcat_plan');
    const seleccionPrevia = select.value;
    select.innerHTML = subsFiltradas.length === 0
        ? `<option value="">Sin subcategorías (créalas en Categorías)</option>`
        : subsFiltradas.map(s => `<option value="${s.ID_Subcategoria}">${esc(s.Nombre_Subcategoria)}</option>`).join('');
    if (subsFiltradas.some(s => String(s.ID_Subcategoria) === seleccionPrevia)) select.value = seleccionPrevia;
}

// Selecciona categoría y subcategoría a partir del ID de la subcategoría (al editar)
function seleccionarSubcategoria(idSub) {
    const sub = subcategorias.find(s => s.ID_Subcategoria === idSub);
    if (!sub) return;
    document.getElementById('id_cat_plan').value = sub.ID_Categoria;
    poblarSubcategorias();
    document.getElementById('id_subcat_plan').value = idSub;
}

document.getElementById('id_cat_plan').addEventListener('change', poblarSubcategorias);

function ajustarFormulario() {
    const tipo = document.getElementById('tipo_plan').value;
    const diaMesInput = document.getElementById('dia_mes');

    // Un tope presupuestal no tiene día de pago, pero sí periodicidad (mensual o quincenal)
    const esTope = tipo === "Gasto Variable (Presupuesto)";
    if (esTope) {
        diaMesInput.value = "";
        diaMesInput.disabled = true;
    } else {
        diaMesInput.disabled = false;
        document.getElementById('periodicidad_plan').value = 'Mensual';
    }
    document.getElementById('box_periodicidad').classList.toggle('hidden', !esTope);
    document.getElementById('nota_estado').classList.toggle('hidden', esTope);
    actualizarEtiquetaMonto();
    poblarCategorias();
}

function actualizarEtiquetaMonto() {
    const quincenal = document.getElementById('tipo_plan').value === "Gasto Variable (Presupuesto)"
        && document.getElementById('periodicidad_plan').value === 'Quincenal';
    document.getElementById('lbl_monto_plan').innerText = quincenal ? 'Monto por quincena ($)' : 'Monto ($)';
}

document.getElementById('periodicidad_plan').addEventListener('change', actualizarEtiquetaMonto);

// ---------- Vigencia (por meses, formato "YYYY-MM") ----------

function mesActual() {
    return fechaHoyISO().slice(0, 7);
}

// "2026-10-01" -> "oct 2026"
function textoMes(fecha) {
    const [anio, mes] = String(fecha).slice(0, 7).split('-').map(Number);
    return new Date(anio, mes - 1, 1).toLocaleDateString('es-CO', { month: 'short', year: 'numeric' }).replace('.', '').replace(' de ', ' ');
}

function textoVigencia(p) {
    if (!p.Fecha_Inicio) return 'Sin fecha de inicio';
    if (p.Fecha_Fin && p.Fecha_Fin.slice(0, 7) === p.Fecha_Inicio.slice(0, 7)) return `Solo ${textoMes(p.Fecha_Inicio)}`;
    return `${textoMes(p.Fecha_Inicio)} → ${p.Fecha_Fin ? textoMes(p.Fecha_Fin) : 'indefinido'}`;
}

// Texto y color del estado de este mes, calculado por el backend a partir de los movimientos
function celdaEstadoMes(p, resumen) {
    if (p.Activo === 'No') return '<span class="text-xs font-bold px-2 py-1 rounded bg-gray-200 text-gray-600">Pausado</span>';

    // Fuera de vigencia este mes: no aparece en el resumen
    const hoy = mesActual();
    if (p.Fecha_Inicio && p.Fecha_Inicio.slice(0, 7) > hoy) {
        return `<span class="text-xs font-bold px-2 py-1 rounded bg-blue-50 text-blue-700">Inicia ${textoMes(p.Fecha_Inicio)}</span>`;
    }
    if (p.Fecha_Fin && p.Fecha_Fin.slice(0, 7) < hoy) {
        return '<span class="text-xs font-bold px-2 py-1 rounded bg-gray-200 text-gray-600">Finalizado</span>';
    }

    if (p.Tipo === "Gasto Variable (Presupuesto)") {
        const b = resumen.presupuestos.find(x => x.id_registro === p.ID_Registro);
        if (!b) return '-';
        const ajuste = b.ajustado ? `<span class="block text-xs text-gray-400">tope este mes ${formatoMoneda(b.valor_periodo)}${b.quincenas ? ' por quincena' : ''}</span>` : '';
        if (b.quincenas) {
            // Una línea por quincena
            return b.quincenas.map(q => `<span class="block text-xs ${q.excedido ? 'text-red-600 font-bold' : 'text-gray-600'}">Q${q.numero}: ${q.porcentaje}% usado</span>`).join('') + ajuste;
        }
        const clase = b.excedido ? 'text-red-600 font-bold' : 'text-gray-600';
        return `<span class="${clase}">${b.porcentaje}% usado</span>${ajuste}`;
    }

    const f = resumen.fijos.find(x => x.id_registro === p.ID_Registro);
    if (!f) return '-';
    const esIngreso = f.tipo_movimiento === 'Ingreso';
    const estados = {
        pagado:    [esIngreso ? 'Recibido' : 'Pagado', 'bg-green-100 text-green-800'],
        parcial:   ['Parcial', 'bg-yellow-100 text-yellow-800'],
        pendiente: ['Pendiente', 'bg-gray-100 text-gray-700'],
        vencido:   [esIngreso ? 'Atrasado' : 'Vencido', 'bg-red-100 text-red-800'],
    };
    const [texto, clase] = estados[f.estado];
    const ajuste = f.ajustado ? `<span class="block text-xs text-gray-400 mt-1">este mes ${formatoMoneda(f.monto)}</span>` : '';
    return `<span class="text-xs font-bold px-2 py-1 rounded ${clase}">${texto}</span>${ajuste}`;
}

async function cargarConfiguracion() {
    try {
        const dataCat = await api(RUTA_CAT);
        categorias = dataCat.categorias;
        subcategorias = dataCat.subcategorias;
    } catch (err) {
        return alert(err.message);
    }
    document.getElementById('mes_inicio').value = mesActual();
    ajustarFormulario();
    cargarPlanificacion();
}

async function cargarPlanificacion() {
    const hoy = new Date();
    let resumen;
    try {
        [registrosPlan, resumen] = await Promise.all([
            api(RUTA_PLAN),
            api(`/dashboard/resumen/${hoy.getMonth() + 1}/${hoy.getFullYear()}`),
        ]);
    } catch (err) {
        return alert(err.message);
    }

    // Tras guardar/editar/pausar/eliminar, el calendario también debe reflejar el cambio
    if (vistaActual === 'calendario') dibujarCalendario();

    const tabla = document.getElementById('tablaPlan');
    if (registrosPlan.length === 0) {
        tabla.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-gray-400 italic">Aún no hay conceptos planificados.</td></tr>';
        return;
    }

    tabla.innerHTML = registrosPlan.map(p => {
        let color = p.Tipo === "Ingreso Fijo" ? "bg-green-100 text-green-800" : (p.Tipo === "Gasto Fijo" ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800");
        const pausado = p.Activo === 'No';
        return `
        <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors ${pausado ? 'opacity-50' : ''}">
            <td class="py-3 px-4"><span class="py-1 px-2.5 rounded-md text-xs font-bold ${color}">${esc(p.Tipo)}</span></td>
            <td class="py-3 px-4 font-medium text-gray-800">
                ${esc(p.Nombre_Concepto)}${p.Dia_Mes ? ` <span class="text-xs text-gray-400">(día ${p.Dia_Mes})</span>` : ''}${p.Periodicidad === 'Quincenal' ? ' <span class="text-xs text-blue-600">(por quincena)</span>' : ''}
                <span class="block text-xs font-normal text-gray-400">${textoVigencia(p)}</span>
            </td>
            <td class="py-3 px-4 font-bold text-gray-900">${formatoMoneda(p.Monto)}</td>
            <td class="py-3 px-4">${celdaEstadoMes(p, resumen)}</td>
            <td class="py-3 px-4 whitespace-nowrap">
                <button type="button" onclick="prepararEdicion(${p.ID_Registro})" class="text-blue-600 hover:text-blue-800 font-bold text-sm bg-blue-50 px-3 py-1 rounded-lg transition-colors">Editar</button>
                <button type="button" onclick="cambiarActivo(${p.ID_Registro}, '${pausado ? 'Sí' : 'No'}')" class="text-gray-600 hover:text-gray-800 font-bold text-sm bg-gray-100 px-3 py-1 rounded-lg transition-colors ml-1">${pausado ? 'Activar' : 'Pausar'}</button>
                <button type="button" onclick="eliminarRegistro(${p.ID_Registro})" class="text-red-600 hover:text-red-800 font-bold text-sm bg-red-50 px-3 py-1 rounded-lg transition-colors ml-1">Eliminar</button>
            </td>
        </tr>`;
    }).join('');
}

function salirDeEdicion() {
    modoEdicion = false;
    idRegistroEditando = null;
    document.getElementById('planForm').reset();
    document.getElementById('mes_inicio').value = mesActual();
    ajustarFormulario();

    const btnSubmit = document.querySelector('#planForm button[type="submit"]');
    btnSubmit.innerText = "Guardar Planificación";
    btnSubmit.classList.replace('bg-blue-600', 'bg-orange-500');
    document.getElementById('btn_cancelar_plan').classList.add('hidden');
}

// Función global para pasar los datos al formulario
window.prepararEdicion = function(id) {
    const p = registrosPlan.find(r => r.ID_Registro === id);
    if (!p) return;

    modoEdicion = true;
    idRegistroEditando = id;

    document.getElementById('tipo_plan').value = p.Tipo;
    document.getElementById('nombre_concepto').value = p.Nombre_Concepto;
    document.getElementById('monto_plan').value = p.Monto;

    // Primero ajustar el formulario según el tipo (filtra subcategorías)...
    ajustarFormulario();
    document.getElementById('periodicidad_plan').value = p.Periodicidad === 'Quincenal' ? 'Quincenal' : 'Mensual';
    actualizarEtiquetaMonto();
    // ...y luego restaurar los valores guardados para no sobrescribirlos
    seleccionarSubcategoria(p.ID_Subcategoria);
    document.getElementById('dia_mes').value = p.Dia_Mes ?? '';
    document.getElementById('mes_inicio').value = p.Fecha_Inicio ? p.Fecha_Inicio.slice(0, 7) : mesActual();
    document.getElementById('mes_fin').value = p.Fecha_Fin ? p.Fecha_Fin.slice(0, 7) : '';

    const btnSubmit = document.querySelector('#planForm button[type="submit"]');
    btnSubmit.innerText = "Actualizar Registro";
    btnSubmit.classList.replace('bg-orange-500', 'bg-blue-600');
    document.getElementById('btn_cancelar_plan').classList.remove('hidden');

    // Desplazar la vista hacia el formulario (el scroll está en <main>, no en window)
    document.getElementById('planForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Pausar un concepto lo saca del resumen y la proyección sin borrarlo
window.cambiarActivo = async function(id, activo) {
    try {
        await api(`${RUTA_PLAN}${id}/activo`, { method: "PUT", body: { activo } });
        cargarPlanificacion();
    } catch (err) {
        alert(err.message);
    }
}

window.eliminarRegistro = async function(id) {
    if (!confirm("¿Eliminar este concepto de la planificación?")) return;
    try {
        await api(`${RUTA_PLAN}${id}`, { method: "DELETE" });
        if (idRegistroEditando === id) salirDeEdicion();
        cargarPlanificacion();
    } catch (err) {
        alert(err.message);
    }
}

document.getElementById('btn_cancelar_plan').addEventListener('click', salirDeEdicion);

document.getElementById('planForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const dia = document.getElementById('dia_mes').value;
    const idSub = parseInt(document.getElementById('id_subcat_plan').value);
    if (isNaN(idSub)) return alert("Selecciona una subcategoría (créala primero en Categorías si no existe).");

    const mesInicio = document.getElementById('mes_inicio').value;
    const mesFin = document.getElementById('mes_fin').value;
    if (!mesInicio) return alert("Indica desde qué mes aplica.");
    if (mesFin && mesFin < mesInicio) return alert("El mes final no puede ser anterior al mes de inicio.");

    const p = {
        tipo: document.getElementById('tipo_plan').value,
        nombre_concepto: document.getElementById('nombre_concepto').value,
        monto: parseFloat(document.getElementById('monto_plan').value),
        dia_mes: dia ? parseInt(dia) : null,
        id_subcategoria: idSub,
        fecha_inicio: `${mesInicio}-01`,
        fecha_fin: mesFin ? `${mesFin}-01` : null,
        periodicidad: document.getElementById('periodicidad_plan').value,
        activo: "Sí"
    };

    try {
        if (modoEdicion) {
            await api(`${RUTA_PLAN}${idRegistroEditando}`, { method: "PUT", body: p });
        } else {
            await api(RUTA_PLAN, { method: "POST", body: p });
        }
        salirDeEdicion();
        cargarPlanificacion();
    } catch (err) {
        alert(err.message);
    }
});

// ---------- Vista calendario ----------

let vistaActual = 'lista';
let calAnio = new Date().getFullYear();
let calMes = new Date().getMonth() + 1; // 1-12
let peticionCalendario = 0;

function cambiarVista(vista) {
    vistaActual = vista;
    try { localStorage.setItem('optifin_vista_plan', vista); } catch (e) { /* sin almacenamiento: no pasa nada */ }

    document.getElementById('vista_lista').classList.toggle('hidden', vista !== 'lista');
    document.getElementById('vista_calendario').classList.toggle('hidden', vista !== 'calendario');
    for (const [id, v] of [['btn_vista_lista', 'lista'], ['btn_vista_calendario', 'calendario']]) {
        const boton = document.getElementById(id);
        boton.classList.toggle('bg-white', v === vista);
        boton.classList.toggle('shadow-sm', v === vista);
        boton.classList.toggle('text-gray-800', v === vista);
        boton.classList.toggle('text-gray-500', v !== vista);
    }
    if (vista === 'calendario') dibujarCalendario();
}

function moverMes(delta) {
    calMes += delta;
    if (calMes < 1) { calMes = 12; calAnio--; }
    if (calMes > 12) { calMes = 1; calAnio++; }
    dibujarCalendario();
}

// Un pago/cobro dentro del día: pendiente -> enlace para registrarlo; pagado -> tachado
function chipFijo(f) {
    const esIngreso = f.tipo_movimiento === 'Ingreso';
    const pagado = f.estado === 'pagado';
    let clase = esIngreso ? 'bg-green-50 text-green-800 border-l-2 border-green-500' : 'bg-red-50 text-red-700 border-l-2 border-red-500';
    if (f.estado === 'vencido') clase = 'bg-red-100 text-red-800 border-l-2 border-red-700 ring-1 ring-red-200 font-bold';
    if (pagado) clase = 'bg-gray-100 text-gray-400 border-l-2 border-gray-300';

    // Pendiente: lo que falta; pagado: lo que se pagó
    const monto = pagado ? f.pagado : f.faltante;
    const contenido = `
        <span class="block truncate ${pagado ? 'line-through' : ''}">${pagado ? '✓ ' : ''}${esc(f.concepto)}</span>
        <span class="block font-semibold">${esIngreso ? '+' : '-'}${formatoMoneda(monto)}</span>`;
    const base = `rounded px-1.5 py-1 text-[11px] leading-tight ${clase}`;
    const titulo = `${f.concepto} · ${formatoMoneda(f.monto)}${f.ajustado ? ' (ajustado este mes)' : ''}`;

    return pagado
        ? `<div class="${base}" title="${esc(titulo)} · ${esIngreso ? 'recibido' : 'pagado'}">${contenido}</div>`
        : `<a href="${enlaceRegistrarFijo(f)}" class="${base} block hover:ring-2 hover:ring-blue-300" title="${esc(titulo)} · clic para registrar el ${esIngreso ? 'cobro' : 'pago'}">${contenido}</a>`;
}

async function dibujarCalendario() {
    const titulo = new Date(calAnio, calMes - 1, 1)
        .toLocaleDateString('es-CO', { month: 'long', year: 'numeric' }).replace(' de ', ' ');
    document.getElementById('cal_titulo').innerText = titulo;

    // Si se navega rápido, solo se dibuja la respuesta de la última petición
    const miPeticion = ++peticionCalendario;
    let resumen;
    try {
        resumen = await api(`/dashboard/resumen/${calMes}/${calAnio}`);
    } catch (err) {
        return alert(err.message);
    }
    if (miPeticion !== peticionCalendario) return;

    // Fijos con día -> en su celda; sin día -> lista aparte
    const porDia = {};
    for (const f of resumen.fijos.filter(f => f.dia_mes)) {
        const dia = Number(f.vencimiento.slice(8, 10)); // día 31 en meses cortos ya viene ajustado al último día
        (porDia[dia] ||= []).push(f);
    }

    const diasDelMes = new Date(calAnio, calMes, 0).getDate();
    const desfase = (new Date(calAnio, calMes - 1, 1).getDay() + 6) % 7; // semana empieza el lunes
    const hoy = fechaHoyISO();
    const celdaVacia = '<div class="min-h-[6.5rem] rounded-lg bg-gray-50"></div>';

    let celdas = celdaVacia.repeat(desfase);
    for (let dia = 1; dia <= diasDelMes; dia++) {
        const iso = `${calAnio}-${String(calMes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
        const esHoy = iso === hoy;
        const items = porDia[dia] || [];
        celdas += `
            <div class="min-h-[6.5rem] rounded-lg border p-1 flex flex-col gap-1 ${esHoy ? 'border-blue-500 ring-1 ring-blue-300 bg-blue-50/30' : 'border-gray-100'}">
                <div class="text-xs font-bold ${esHoy ? 'text-blue-600' : 'text-gray-400'}">${dia}${esHoy ? ' · hoy' : ''}</div>
                ${items.map(chipFijo).join('')}
            </div>`;
    }
    celdas += celdaVacia.repeat((7 - (desfase + diasDelMes) % 7) % 7);
    document.getElementById('cal_grilla').innerHTML = celdas;

    // Totales del mes
    const suma = (lista, campo) => lista.reduce((s, f) => s + f[campo], 0);
    const cobros = resumen.fijos.filter(f => f.tipo_movimiento === 'Ingreso');
    const pagos = resumen.fijos.filter(f => f.tipo_movimiento === 'Gasto');
    document.getElementById('cal_totales').innerHTML = `
        <span class="text-gray-500">Cobros: <b class="text-green-700">${formatoMoneda(suma(cobros, 'monto'))}</b></span>
        <span class="text-gray-500">Pagos: <b class="text-red-600">${formatoMoneda(suma(pagos, 'monto'))}</b></span>
        <span class="text-gray-500">Falta pagar: <b class="text-gray-800">${formatoMoneda(suma(pagos, 'faltante'))}</b></span>`;

    // Fijos sin día y topes presupuestales del mes
    const sinDia = resumen.fijos.filter(f => !f.dia_mes);
    const bloques = [];
    if (sinDia.length) {
        bloques.push(`<p class="text-xs font-bold uppercase text-gray-500 mb-1">Sin día fijo este mes</p>
            <div class="flex flex-wrap gap-2">${sinDia.map(f => `<div class="w-40">${chipFijo(f)}</div>`).join('')}</div>`);
    }
    if (resumen.presupuestos.length) {
        bloques.push(`<p class="text-xs font-bold uppercase text-gray-500 mt-3 mb-1">Topes presupuestales del mes</p>
            <div class="flex flex-wrap gap-2">${resumen.presupuestos.map(p => {
                // Quincenal: una línea por quincena; mensual: una sola
                const lineas = (p.quincenas || [{ ...p, rango: null }]).map(q => `
                    <span class="block">${q.rango ? `${q.rango}: ` : ''}<b>${formatoMoneda(q.gastado)}</b> de ${formatoMoneda(q.tope)}
                    <span class="${q.excedido ? 'text-red-600 font-bold' : 'text-blue-500'}">(${q.porcentaje}%)</span></span>`).join('');
                return `<div class="rounded px-2 py-1 text-xs bg-blue-50 text-blue-800 border-l-2 border-blue-400">
                    <span class="block font-semibold">${esc(p.concepto)}${p.quincenas ? ' · por quincena' : ''}</span>${lineas}
                </div>`;
            }).join('')}</div>`);
    }
    if (resumen.fijos.length === 0 && resumen.presupuestos.length === 0) {
        bloques.push('<p class="text-sm text-gray-400 italic">No hay nada planificado para este mes.</p>');
    }
    document.getElementById('cal_sin_dia').innerHTML = bloques.join('');
}

document.getElementById('btn_vista_lista').addEventListener('click', () => cambiarVista('lista'));
document.getElementById('btn_vista_calendario').addEventListener('click', () => cambiarVista('calendario'));
document.getElementById('cal_anterior').addEventListener('click', () => moverMes(-1));
document.getElementById('cal_siguiente').addEventListener('click', () => moverMes(1));
document.getElementById('cal_hoy').addEventListener('click', () => {
    calAnio = new Date().getFullYear();
    calMes = new Date().getMonth() + 1;
    dibujarCalendario();
});

// Recordar la última vista elegida
let vistaGuardada = 'lista';
try { vistaGuardada = localStorage.getItem('optifin_vista_plan') || 'lista'; } catch (e) { /* sin almacenamiento */ }
cambiarVista(vistaGuardada === 'calendario' ? 'calendario' : 'lista');

cargarConfiguracion();
