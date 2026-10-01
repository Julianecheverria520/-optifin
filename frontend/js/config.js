// Configuración compartida por todas las páginas. 
const API_URL = "https://optifin-bhok.onrender.com";

// --- SISTEMA DE SESIÓN ---
let USUARIO_ACTUAL = null;
const esPaginaLogin = window.location.pathname.endsWith('login.html');

// Lee la sesión de localStorage (si eligió "mantener sesión") o de sessionStorage.
// Si el almacenamiento no está disponible o el dato está dañado, se trata como "sin sesión".
function leerSesion() {
    for (const almacen of [() => localStorage, () => sessionStorage]) {
        try {
            const texto = almacen().getItem('optifin_user');
            if (!texto) continue;
            let usuario = JSON.parse(texto);

            // Adaptación de variables
            if (usuario.ID_Usuario && !usuario.id) usuario.id = usuario.ID_Usuario;
            if (usuario.Nombre && !usuario.nombre) usuario.nombre = usuario.Nombre;
            if (usuario.Email && !usuario.email) usuario.email = usuario.Email;

            // EL CAMBIO CLAVE: Ya no exigimos usuario.nombre para dejarte pasar
            if (usuario && usuario.id && usuario.token) return usuario;
            
            almacen().removeItem('optifin_user'); 
        } catch (e) { }
    }
    return null;
}

USUARIO_ACTUAL = leerSesion();

if (USUARIO_ACTUAL) {
    // Si ya inició sesión y entra al login, enviarlo al resumen
    if (esPaginaLogin) window.location.replace('dashboard.html');
} else if (!esPaginaLogin) {
    // Sin sesión: al login (replace para que "atrás" no vuelva a una página protegida)
    window.location.replace('login.html');
}

window.cerrarSesion = function() {
    try { localStorage.removeItem('optifin_user'); } catch (e) { /* sin almacenamiento */ }
    try { sessionStorage.removeItem('optifin_user'); } catch (e) { /* sin almacenamiento */ }
    window.location.replace('login.html');
};
// -------------------------

async function api(ruta, opciones = {}) {
    // El token de la sesión identifica al usuario ante el backend (cada uno ve solo sus datos)
    const autenticacion = USUARIO_ACTUAL ? { "Authorization": `Bearer ${USUARIO_ACTUAL.token}` } : {};
    const config = { ...opciones, headers: { "Content-Type": "application/json", ...autenticacion, ...(opciones.headers || {}) } };
    if (config.body !== undefined && typeof config.body !== "string") {
        config.body = JSON.stringify(config.body);
    }

    let res;
    try {
        res = await fetch(API_URL + ruta, config);
    } catch (err) {
        throw new Error("No hay conexión con el servidor. ¿Está corriendo el backend?");
    }

    const data = await res.json().catch(() => null);
    // Sesión vencida o inválida: volver al login (en el login, el 401 es "contraseña incorrecta")
    if (res.status === 401 && !esPaginaLogin) {
        window.cerrarSesion();
        throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
    }
    if (!res.ok) {
        throw new Error(mensajeDeError(data) || `Error del servidor (${res.status})`);
    }
    return data;
}

function mensajeDeError(data) {
    if (!data || !data.detail) return null;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
        return data.detail.map(d => {
            const msg = String(d.msg);
            // Nuestros mensajes (en español) se muestran tal cual; los genéricos, con el campo
            if (msg.startsWith("Value error, ")) return msg.replace(/^Value error, /, "");
            const campo = d.loc && d.loc.length > 1 ? `${d.loc[d.loc.length - 1]}: ` : "";
            return campo + msg;
        }).join("\n");
    }
    return null;
}

function esc(valor) {
    return String(valor ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function formatoMoneda(valor) {
    const n = Number(valor || 0);
    return (n < 0 ? "-$" : "$") + Math.abs(n).toLocaleString("es-CO");
}

function enlaceRegistrarFijo(f) {
    const hoy = fechaHoyISO();
    const fecha = f.vencimiento.slice(0, 7) === hoy.slice(0, 7) ? hoy : f.vencimiento;
    const params = new URLSearchParams({
        tipo: f.tipo_movimiento,
        sub: f.id_subcategoria,
        monto: f.faltante,
        desc: f.concepto,
        fecha: fecha,
    });
    return `index.html?${params}`;
}

function fechaHoyISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}