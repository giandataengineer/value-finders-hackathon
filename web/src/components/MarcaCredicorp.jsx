/* Marca de Credicorp Capital: triángulo oscuro y triángulo rojo superpuesto, más el nombre. Es una reproducción vectorial de la marca
   de las diapositivas del reto; conviene sustituirla por el archivo oficial de la empresa. */
export function TrianguloCredicorp({ size = 26 }) {
  return (
    <svg width={size} height={size * 0.86} viewBox="0 0 44 38" aria-hidden="true">
      <polygon points="1,37 19,2 30,37" fill="#141414" />
      <polygon points="20,37 32,15 43,37" fill="#d3222e" />
    </svg>
  );
}

export function MarcaCredicorp({ compacta = false }) {
  return (
    <span className="marca-cc">
      <TrianguloCredicorp />
      {!compacta && <span className="marca-cc__nombre">Credicorp<span>Capital</span></span>}
    </span>
  );
}
