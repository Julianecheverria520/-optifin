// Configuración compartida por todas las páginas. 
// El mismo servidor que entrega las páginas atiende la API: en Render es Render y en local es tu
// uvicorn. Así nunca se mezclan (antes, abrir la app en local modificaba los datos de producción).
// Si abres el HTML directo desde el disco (file://) o con otro servidor local (p. ej. Live Server
// en el puerto 5500), se usa el backend local del puerto 8000. Nunca se apunta a producción desde local.
const ES_LOCAL = window.location.protocol === "file:" || ["127.0.0.1", "localhost"].includes(window.location.hostname);
const API_URL = ES_LOCAL && window.location.port !== "8000" ? "http://127.0.0.1:8000" : "";

// --- SISTEMA DE SESIÓN ---
// La sesión guarda: id, nombre, email, token (dura 60 min), refresh_token y expira (segundos Unix).
// Con "Mantener sesión" va en localStorage (sobrevive al cerrar el navegador); si no, en sessionStorage.
let USUARIO_ACTUAL = null;
let ALMACEN_SESION = null;
const esPaginaLogin = window.location.pathname.endsWith('login.html');

function leerSesion() {
    for (const almacen of [() => localStorage, () => sessionStorage]) {
        try {
            const texto = almacen().getItem('optifin_user');
            if (!texto) continue;
            const usuario = JSON.parse(texto);
            if (usuario && usuario.id && usuario.token) {
                ALMACEN_SESION = almacen();
                return usuario;
            }
            almacen().removeItem('optifin_user'); // dato inválido
        } catch (e) { /* almacenamiento bloqueado o JSON dañado */ }
    }
    return null;
}

function guardarSesion() {
    try { (ALMACEN_SESION || sessionStorage).setItem('optifin_user', JSON.stringify(USUARIO_ACTUAL)); } catch (e) { /* sin almacenamiento */ }
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

// Renueva el token con el refresh token. Si varias peticiones lo necesitan a la vez, comparten
// la misma renovación. Devuelve true si quedó una sesión válida.
let renovacionEnCurso = null;
function renovarSesion() {
    if (!USUARIO_ACTUAL || !USUARIO_ACTUAL.refresh_token) return Promise.resolve(false);
    if (!renovacionEnCurso) {
        renovacionEnCurso = fetch(API_URL + "/auth/renovar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: USUARIO_ACTUAL.refresh_token }),
        })
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (!data || !data.token) return false;
                Object.assign(USUARIO_ACTUAL, { token: data.token, refresh_token: data.refresh_token, expira: data.expira });
                guardarSesion();
                return true;
            })
            .catch(() => false)
            .finally(() => { renovacionEnCurso = null; });
    }
    return renovacionEnCurso;
}

// Renueva un minuto antes de que expire, para no llegar a un 401
async function asegurarToken() {
    if (USUARIO_ACTUAL && USUARIO_ACTUAL.expira && USUARIO_ACTUAL.expira - Date.now() / 1000 < 60) {
        await renovarSesion();
    }
}
// -------------------------

async function api(ruta, opciones = {}, reintento = false) {
    if (!esPaginaLogin) await asegurarToken();

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
        throw new Error("No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.");
    }

    // Sesión vencida o inválida (en el login, el 401 es "contraseña incorrecta"):
    // se intenta renovar una vez y repetir la petición; si no se puede, al login
    if (res.status === 401 && !esPaginaLogin) {
        if (!reintento && await renovarSesion()) return api(ruta, opciones, true);
        window.cerrarSesion();
        throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) {
        const error = new Error(mensajeDeError(data) || `Error del servidor (${res.status})`);
        error.status = res.status;
        throw error;
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