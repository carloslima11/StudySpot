// Só aceita numeros e tem formatação
const codigo = document.getElementById("codigo");

if (codigo) {
  codigo.addEventListener("input", () => {
    let v = codigo.value.replace(/\D/g, "").slice(0, 6);
    if (v.length > 3) v = v.slice(0, 3) + " " + v.slice(3);
    codigo.value = v;
  });
}