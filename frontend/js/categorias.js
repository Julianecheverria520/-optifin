const RUTA_CAT = "/categorias/";

async function cargarDatos() {
    let data;
    try {
        data = await api(RUTA_CAT);
    } catch (err) {
        return alert(err.message);
    }

    const select = document.getElementById('id_categoria_padre');
    const seleccionPrevia = select.value;
    select.innerHTML = data.categorias.map(c => `<option value="${c.ID_Categoria}">${esc(c.Nombre_Categoria)} (${esc(c.Tipo_Movimiento)})</option>`).join('');
    if (data.categorias.some(c => String(c.ID_Categoria) === seleccionPrevia)) select.value = seleccionPrevia;

    const lista = document.getElementById('listaCategorias');
    if (data.categorias.length === 0) {
        lista.innerHTML = `
            <p class="text-sm text-gray-500 mb-3">Aún no tienes categorías. Puedes empezar con las estándar de OptiFin y ajustarlas a tu gusto.</p>
            <button type="button" onclick="cargarPlantilla()" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">Cargar categorías estándar</button>`;
        return;
    }

    lista.innerHTML = data.categorias.map(cat => {
        const subsDeCat = data.subcategorias.filter(s => s.ID_Categoria === cat.ID_Categoria);
        const items = subsDeCat.length === 0
            ? `<li class="text-sm text-gray-400 italic">Sin subcategorías</li>`
            : subsDeCat.map(sub => `
                <li class="flex justify-between items-center text-sm text-gray-600 border-b pb-1 last:border-0">
                    <span>↳ ${esc(sub.Nombre_Subcategoria)}</span>
                    <button type="button" onclick="eliminarSubcategoria(${sub.ID_Subcategoria})" class="text-xs text-red-500 hover:text-red-700">Eliminar</button>
                </li>`).join('');

        return `
            <div class="border rounded-lg overflow-hidden shadow-sm">
                <div class="bg-gray-100 p-3 font-bold text-gray-800 flex justify-between items-center gap-2">
                    <span>${esc(cat.Nombre_Categoria)}</span>
                    <div class="flex items-center gap-3">
                        <span class="text-xs px-2 py-1 ${cat.Tipo_Movimiento === 'Ingreso' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'} rounded-full">${esc(cat.Tipo_Movimiento)}</span>
                        <button type="button" onclick="eliminarCategoria(${cat.ID_Categoria})" class="text-xs font-normal text-red-500 hover:text-red-700">Eliminar</button>
                    </div>
                </div>
                <ul class="p-3 bg-white space-y-2">${items}</ul>
            </div>`;
    }).join('');
}

window.cargarPlantilla = async function() {
    try {
        const r = await api(`${RUTA_CAT}plantilla`, { method: "POST" });
        alert(r.mensaje);
        cargarDatos();
    } catch (err) {
        alert(err.message);
    }
}

window.eliminarCategoria = async function(id) {
    if (!confirm("¿Eliminar esta categoría?")) return;
    try {
        await api(`${RUTA_CAT}${id}`, { method: "DELETE" });
        cargarDatos();
    } catch (err) {
        alert(err.message);
    }
}

window.eliminarSubcategoria = async function(id) {
    if (!confirm("¿Eliminar esta subcategoría?")) return;
    try {
        await api(`${RUTA_CAT}subcategoria/${id}`, { method: "DELETE" });
        cargarDatos();
    } catch (err) {
        alert(err.message);
    }
}

document.getElementById('catForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const cat = {
        nombre_categoria: document.getElementById('nombre_cat').value,
        tipo_movimiento: document.getElementById('tipo_cat').value
    };
    try {
        await api(RUTA_CAT, { method: "POST", body: cat });
        document.getElementById('catForm').reset();
        cargarDatos();
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('subForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const idPadre = parseInt(document.getElementById('id_categoria_padre').value);
    if (isNaN(idPadre)) return alert("Primero crea una categoría principal.");

    const sub = {
        id_categoria: idPadre,
        nombre_subcategoria: document.getElementById('nombre_sub').value
    };
    try {
        await api(`${RUTA_CAT}subcategoria`, { method: "POST", body: sub });
        document.getElementById('nombre_sub').value = '';  // Conservar la categoría elegida para añadir varias seguidas
        cargarDatos();
    } catch (err) {
        alert(err.message);
    }
});

cargarDatos();
