// Página "Día a día": gastos del mes por día (fijos vs. diarios), filtro por categoría
// y el dinero en cuentas al cierre de cada día. Son dos gráficas separadas a propósito:
// gastos y saldo tienen escalas muy distintas y no deben compartir eje.

let datosMes = null;
const categoriasElegidas = new Set();   // vacío = todas
let graficaGastos = null;
let graficaSaldo = null;

const estilo = getComputedStyle(document.querySelector('.viz'));
const color = nombre => estilo.getPropertyValue(nombre).trim();
const COLORES = {
    fijos: color('--serie-fijos'), diarios: color('--serie-diarios'), saldo: color('--serie-saldo'),
    rejilla: color('--rejilla'), eje: color('--texto-eje'), tarjeta: '#fffdf9',
};

// $1.250.000 -> "$1,3 M"; $85.000 -> "$85 mil"
function monedaCorta(v) {
    const a = Math.abs(v);
    if (a >= 1e6) return `${v < 0 ? '-' : ''}$${(a / 1e6).toLocaleString('es-CO', { maximumFractionDigits: 1 })} M`;
    if (a >= 1e3) return `${v < 0 ? '-' : ''}$${Math.round(a / 1e3).toLocaleString('es-CO')} mil`;
    return formatoMoneda(v);
}

function establecerMesActual() {
    const hoy = new Date();
    const selectAnio = document.getElementById('anioSelect');
    const anios = [];
    for (let a = hoy.getFullYear() - 3; a <= hoy.getFullYear() + 1; a++) anios.push(a);
    selectAnio.innerHTML = anios.map(a => `<option value="${a}">${a}</option>`).join('');
    selectAnio.value = hoy.getFullYear();
    document.getElementById('mesSelect').value = hoy.getMonth() + 1;
}

async function cargarMes() {
    const mes = document.getElementById('mesSelect').value;
    const anio = document.getElementById('anioSelect').value;
    try {
        datosMes = await api(`/dashboard/diario/${mes}/${anio}`);
    } catch (err) {
        return alert(err.message);
    }
    // Conservar solo las categorías elegidas que existan en el mes nuevo
    const existentes = new Set(datosMes.categorias.map(c => String(c.id)));
    for (const id of [...categoriasElegidas]) if (!existentes.has(id)) categoriasElegidas.delete(id);
    dibujarSaldos();
    dibujarChips();
    dibujarGastos();
}

function dibujarSaldos() {
    const d = datosMes;
    document.getElementById('d_saldo_inicial').innerText = formatoMoneda(d.saldo_inicial);
    document.getElementById('d_saldo_final_titulo').innerText = d.saldo_final_es_hoy ? 'Saldo hoy' : 'Saldo final';
    document.getElementById('d_saldo_final').innerText = formatoMoneda(d.saldo_final);
    const variacion = d.saldo_final - d.saldo_inicial;
    const el = document.getElementById('d_variacion');
    el.innerText = Math.abs(variacion) < 1 ? 'Sin cambio en el mes'
        : `${variacion > 0 ? 'Subió' : 'Bajó'} ${formatoMoneda(Math.abs(variacion))} en el mes`;
    el.className = `text-xs mt-1 font-semibold ${variacion < 0 ? 'text-red-600' : 'text-green-700'}`;
}

function dibujarChips() {
    const cont = document.getElementById('chips_categorias');
    const chip = (id, nombre, activo) =>
        `<button type="button" class="chip-cat text-xs font-bold px-3 py-1.5 rounded-full border border-gray-200 bg-gray-50 text-gray-700" aria-pressed="${activo}" onclick="elegirCategoria(${id === null ? 'null' : `'${esc(id)}'`})">${esc(nombre)}</button>`;
    cont.innerHTML = chip(null, 'Todas', categoriasElegidas.size === 0)
        + datosMes.categorias.map(c => chip(String(c.id), c.nombre, categoriasElegidas.has(String(c.id)))).join('');
}

window.elegirCategoria = function(id) {
    if (id === null) categoriasElegidas.clear();
    else if (categoriasElegidas.has(id)) categoriasElegidas.delete(id);
    else categoriasElegidas.add(id);
    dibujarChips();
    dibujarGastos();
};

function gastosFiltrados() {
    return datosMes.gastos.filter(g => categoriasElegidas.size === 0 || categoriasElegidas.has(String(g.id_categoria)));
}

function dibujarGastos() {
    const d = datosMes;
    const dias = Array.from({ length: d.dias }, (_, i) => i + 1);
    const fijos = new Array(d.dias).fill(0);
    const diarios = new Array(d.dias).fill(0);
    const detalle = dias.map(() => []);
    for (const g of gastosFiltrados()) {
        (g.fijo ? fijos : diarios)[g.dia - 1] += g.monto;
        detalle[g.dia - 1].push(g);
    }

    const totalFijos = fijos.reduce((a, b) => a + b, 0);
    const totalDiarios = diarios.reduce((a, b) => a + b, 0);
    document.getElementById('d_fijos').innerText = formatoMoneda(totalFijos);
    document.getElementById('d_diarios').innerText = formatoMoneda(totalDiarios);
    const diasTranscurridos = d.hoy || d.dias;
    document.getElementById('d_promedio').innerText = `Promedio ${formatoMoneda(totalDiarios / diasTranscurridos)} por día`;

    dibujarGraficaGastos(dias, fijos, diarios);
    dibujarGraficaSaldo(dias, d.saldos);
    dibujarTabla(dias, fijos, diarios, detalle);
}

const ejes = (formato) => ({
    x: { stacked: true, grid: { display: false }, ticks: { color: COLORES.eje, font: { size: 11 }, maxRotation: 0, autoSkipPadding: 8 } },
    y: { stacked: true, beginAtZero: true, grid: { color: COLORES.rejilla }, border: { display: false },
         ticks: { color: COLORES.eje, font: { size: 11 }, callback: formato, maxTicksLimit: 6 } },
});

function dibujarGraficaGastos(dias, fijos, diarios) {
    const barra = (etiqueta, datos, fondo) => ({
        label: etiqueta, data: datos, backgroundColor: fondo,
        // 2px del color de la tarjeta separan los dos tramos de una misma barra
        borderColor: COLORES.tarjeta, borderWidth: { top: 2 }, borderRadius: 4, borderSkipped: 'bottom',
        maxBarThickness: 22,
    });
    const config = {
        type: 'bar',
        data: { labels: dias, datasets: [barra('Fijos', fijos, COLORES.fijos), barra('Diarios', diarios, COLORES.diarios)] },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            scales: ejes(v => monedaCorta(v)),
            plugins: {
                legend: { display: false },  // la leyenda está en el HTML, junto al título
                tooltip: {
                    filter: item => item.raw > 0,
                    callbacks: {
                        title: items => `Día ${items[0].label}`,
                        label: item => ` ${item.dataset.label}: ${formatoMoneda(item.raw)}`,
                        footer: items => items.length > 1 ? `Total: ${formatoMoneda(items.reduce((s, i) => s + i.raw, 0))}` : '',
                    },
                },
            },
        },
    };
    if (graficaGastos) graficaGastos.destroy();
    graficaGastos = new Chart(document.getElementById('grafica_gastos'), config);
}

function dibujarGraficaSaldo(dias, saldos) {
    const config = {
        type: 'line',
        data: { labels: dias, datasets: [{
            label: 'Dinero en cuentas', data: saldos, borderColor: COLORES.saldo, borderWidth: 2,
            pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: COLORES.saldo,
            pointHoverBorderColor: COLORES.tarjeta, pointHoverBorderWidth: 2, tension: 0, spanGaps: false,
        }] },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            scales: { ...ejes(v => monedaCorta(v)), y: { ...ejes(v => monedaCorta(v)).y, stacked: false, beginAtZero: false } },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { title: items => `Cierre del día ${items[0].label}`, label: item => ` ${formatoMoneda(item.raw)}` } },
            },
        },
    };
    if (graficaSaldo) graficaSaldo.destroy();
    graficaSaldo = new Chart(document.getElementById('grafica_saldo'), config);
}

function dibujarTabla(dias, fijos, diarios, detalle) {
    const filas = dias.filter(dia => fijos[dia - 1] + diarios[dia - 1] > 0);
    const tabla = document.getElementById('tabla_dias');
    if (filas.length === 0) {
        tabla.innerHTML = '<tr><td colspan="6" class="py-6 text-center text-gray-400 italic">No hay gastos en este mes con este filtro.</td></tr>';
        return;
    }
    tabla.innerHTML = filas.map(dia => {
        const i = dia - 1;
        const saldo = datosMes.saldos[i];
        const enQue = detalle[i].map(g => esc(g.descripcion || g.subcategoria)).join(', ');
        return `
            <tr class="border-b border-gray-100">
                <td class="py-2 px-4 font-medium">${dia}</td>
                <td class="py-2 px-4 text-right">${fijos[i] ? formatoMoneda(fijos[i]) : '–'}</td>
                <td class="py-2 px-4 text-right">${diarios[i] ? formatoMoneda(diarios[i]) : '–'}</td>
                <td class="py-2 px-4 text-right font-bold">${formatoMoneda(fijos[i] + diarios[i])}</td>
                <td class="py-2 px-4 text-right text-gray-500">${saldo === null ? '–' : formatoMoneda(saldo)}</td>
                <td class="py-2 px-4 text-gray-500 max-w-xs truncate" title="${enQue}">${enQue}</td>
            </tr>`;
    }).join('');
}

document.getElementById('mesSelect').addEventListener('change', cargarMes);
document.getElementById('anioSelect').addEventListener('change', cargarMes);
establecerMesActual();
cargarMes();
