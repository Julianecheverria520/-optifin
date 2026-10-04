// Service worker de OptiFin: permite instalar la app y que las páginas abran aunque falle la red.
// Estrategia "red primero": siempre se pide la versión nueva al servidor y solo si no hay conexión
// se usa la copia guardada. Así un despliegue nuevo se ve de inmediato.
// NUNCA se guardan respuestas de la API (datos financieros): solo páginas, scripts, estilos e íconos.

const CACHE = "optifin-v4";
const PAGINAS_BASE = ["login.html", "dashboard.html", "index.html", "manifest.json", "css/tailwind.css", "css/styles.css", "iconos/icono-192.png"];

self.addEventListener("install", (evento) => {
    evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PAGINAS_BASE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
    // Borrar cachés de versiones anteriores
    evento.waitUntil(
        caches.keys()
            .then((nombres) => Promise.all(nombres.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
            .then(() => self.clients.claim())
    );
});

// Solo archivos estáticos de la app. Ojo: las rutas de la API terminan en "/" (/cuentas/, /transacciones/),
// así que la barra final NO cuenta como archivo, salvo la raíz exacta.
function esArchivoDeLaApp(url) {
    return url.origin === self.location.origin
        && (/\.(html|js|css|png)$/.test(url.pathname) || url.pathname.endsWith("/manifest.json") || url.pathname === new URL(self.registration.scope).pathname);
}

self.addEventListener("fetch", (evento) => {
    const peticion = evento.request;
    const url = new URL(peticion.url);
    // Solo GET de archivos propios; la API (/cuentas, /deudas, /auth...) siempre va directo al servidor
    if (peticion.method !== "GET" || !esArchivoDeLaApp(url)) return;

    evento.respondWith(
        fetch(peticion)
            .then((respuesta) => {
                if (respuesta.ok) {
                    const copia = respuesta.clone();
                    caches.open(CACHE).then((cache) => cache.put(peticion, copia));
                }
                return respuesta;
            })
            .catch(() => caches.match(peticion).then((guardada) => guardada || caches.match("dashboard.html")))
    );
});
