// Estilos de Tailwind compilados a frontend/css/tailwind.css (ya no se usa el CDN, que algunas redes bloquean).
// Si agregas clases nuevas en los HTML o JS, vuelve a generar el archivo desde la raíz del proyecto:
//   npx tailwindcss@3 -i frontend/css/tailwind.entrada.css -o frontend/css/tailwind.css --minify
module.exports = {
    content: ["./frontend/**/*.html", "./frontend/js/**/*.js"],
    theme: { extend: {} },
    plugins: [],
};
