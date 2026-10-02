// Instalación como app (PWA): registra el service worker y gestiona el botón "Instalar app".
// - Android / Chrome / Edge: el navegador avisa que se puede instalar (beforeinstallprompt) y el
//   botón abre el diálogo nativo de instalación.
// - iPhone / iPad (Safari): no existe ese aviso; el botón muestra cómo agregarla a la pantalla de inicio.
// Los botones de instalar se marcan con la clase "boton-instalar" (están ocultos hasta que aplique).

let avisoInstalacion = null;

const yaInstalada = () =>
    window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
const esIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;

window.mostrarBotonesInstalar = mostrarBotonesInstalar;
function mostrarBotonesInstalar() {
    const visible = !yaInstalada() && (avisoInstalacion !== null || esIOS());
    document.querySelectorAll(".boton-instalar").forEach((b) => b.classList.toggle("hidden", !visible));
}

window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();          // se muestra nuestro botón en vez del aviso automático
    avisoInstalacion = e;
    mostrarBotonesInstalar();
});

window.addEventListener("appinstalled", () => {
    avisoInstalacion = null;
    mostrarBotonesInstalar();
});

window.instalarApp = async function () {
    if (avisoInstalacion) {
        avisoInstalacion.prompt();
        await avisoInstalacion.userChoice;
        avisoInstalacion = null;
        return mostrarBotonesInstalar();
    }
    if (esIOS()) mostrarInstruccionesIOS();
};

function mostrarInstruccionesIOS() {
    if (document.getElementById("modal-ios")) return;
    document.body.insertAdjacentHTML("beforeend", `
        <div id="modal-ios" onclick="if (event.target === this) this.remove()" class="fixed inset-0 z-50 bg-black/50 flex items-end justify-center">
            <div class="bg-white w-full rounded-t-2xl p-6 space-y-3 text-gray-700">
                <div class="flex items-center gap-3">
                    <img src="iconos/icono-192.png" alt="" class="w-12 h-12 rounded-xl">
                    <div><p class="font-bold text-gray-900">Instalar OptiFin</p><p class="text-sm text-gray-500">Úsala como una app desde tu pantalla de inicio</p></div>
                </div>
                <ol class="text-sm space-y-2 list-decimal list-inside">
                    <li>Toca el botón <b>Compartir</b> <span aria-hidden="true">(el cuadrado con la flecha ↑)</span> en la barra de Safari.</li>
                    <li>Elige <b>Agregar a pantalla de inicio</b>.</li>
                    <li>Toca <b>Agregar</b>.</li>
                </ol>
                <button type="button" onclick="document.getElementById('modal-ios').remove()" class="w-full bg-[#111c43] text-white font-bold py-3 rounded-xl">Entendido</button>
            </div>
        </div>`);
}

// El service worker solo funciona en https o en localhost
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => { /* sin SW la app funciona igual */ }));
}

document.addEventListener("DOMContentLoaded", mostrarBotonesInstalar);
