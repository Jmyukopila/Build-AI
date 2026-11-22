/* Fondo vivo compartido por todas las páginas. */
(() => {
  const reducido = matchMedia("(prefers-reduced-motion: reduce)");
  const oscuro = matchMedia("(prefers-color-scheme: dark)");
  /* ══ Fondo vivo ═══════════════════════════════════════════════════════
     Una cuadrícula de puntos sobre el módulo 1:2 de la marca (columna a la izquierda, dos filas a la derecha).
     Los puntos crecen, se apartan y se tiñen de índigo cerca del puntero; un clic lanza una onda; el scroll los desliza. */
  (() => {
    const cv = document.getElementById("fondo");
    if (!cv || !cv.getContext) return;
    const c = cv.getContext("2d");
    const PASO = 30, RADIO = 140;
    const TINTA = { claro: [26, 31, 27], oscuro: [233, 236, 229] };
    const ACENTO = { claro: [75, 63, 176], oscuro: [181, 172, 255] };
    let w = 0, h = 0, dpr = 1, pendiente = false;
    let objetivo = { x: 0, y: 0 }, p = { x: 0, y: 0 };   // posición pedida y suavizada del puntero
    let intensidad = 0, dentro = false;
    let ondas = [];

    function medir() {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      w = innerWidth; h = innerHeight;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    }

    function dibujar() {
      const tema = oscuro.matches ? "oscuro" : "claro";
      const t = TINTA[tema], a = ACENTO[tema];
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, w, h);

      // El módulo de la marca: columna tintada y dos filetes. Sin degradados, solo tono plano.
      const tercio = Math.round(w / 3), mitad = Math.round(h / 2);
      c.fillStyle = `rgba(${a},${tema === "oscuro" ? .055 : .04})`;
      c.fillRect(0, 0, tercio, h);
      c.strokeStyle = `rgba(${t},.07)`; c.lineWidth = 1;
      c.beginPath();
      c.moveTo(tercio + .5, 0); c.lineTo(tercio + .5, h);
      c.moveTo(tercio, mitad + .5); c.lineTo(w, mitad + .5);
      c.stroke();

      const ahora = performance.now();
      const mueve = !reducido.matches;
      const desliza = (scrollY * .12) % PASO;
      const cols = Math.ceil(w / PASO) + 1, filas = Math.ceil(h / PASO) + 2;
      for (let j = -1; j < filas; j++) {
        for (let i = 0; i < cols; i++) {
          let x = i * PASO + PASO / 2, y = j * PASO + PASO / 2 - desliza;
          let fuerza = 0, empuje = 0, dx = 0, dy = 0;

          // Cerca del puntero
          const px = x - p.x, py = y - p.y, d2 = px * px + py * py;
          const k = intensidad * Math.exp(-d2 / (RADIO * RADIO));
          fuerza += k;
          if (mueve && k > .002) { const d = Math.sqrt(d2) || 1; empuje += 13 * k; dx += px / d; dy += py / d; }

          // Ondas de los clics
          for (const o of ondas) {
            const edad = (ahora - o.t) / 1000;
            const ox = x - o.x, oy = y - o.y, d = Math.sqrt(ox * ox + oy * oy) || 1;
            const e = Math.exp(-Math.pow((d - edad * 520) / 42, 2)) * (1 - edad / 1.5);
            if (e > .003) { fuerza += e; empuje += 9 * e; dx += ox / d; dy += oy / d; }
          }

          if (empuje) { const n = Math.hypot(dx, dy) || 1; x += dx / n * empuje; y += dy / n * empuje; }
          const m = Math.min(1, fuerza * 1.5);
          const r = 1.05 + 2.1 * Math.min(1, fuerza);
          const alfa = .2 + .4 * Math.min(1, fuerza);
          c.fillStyle = `rgba(${Math.round(t[0] + (a[0] - t[0]) * m)},${Math.round(t[1] + (a[1] - t[1]) * m)},${Math.round(t[2] + (a[2] - t[2]) * m)},${alfa})`;
          c.beginPath(); c.arc(x, y, r, 0, 6.2832); c.fill();
        }
      }
    }

    // El bucle solo corre mientras algo se mueve (puntero que se asienta, ondas vivas).
    function fotograma() {
      pendiente = false;
      const ahora = performance.now();
      const f = reducido.matches ? 1 : .2;
      p.x += (objetivo.x - p.x) * f; p.y += (objetivo.y - p.y) * f;
      const meta = dentro ? 1 : 0;
      intensidad += (meta - intensidad) * (reducido.matches ? 1 : .12);
      if (Math.abs(meta - intensidad) < .01) intensidad = meta;
      ondas = ondas.filter(o => ahora - o.t < 1500);
      dibujar();
      const sigue = ondas.length || Math.abs(objetivo.x - p.x) > .4 || Math.abs(objetivo.y - p.y) > .4 || intensidad !== meta;
      if (sigue) pedir();
    }
    function pedir() { if (!pendiente) { pendiente = true; requestAnimationFrame(fotograma); } }

    medir(); dibujar();
    addEventListener("resize", () => { medir(); pedir(); });
    addEventListener("scroll", pedir, { passive: true });
    oscuro.addEventListener("change", pedir);
    reducido.addEventListener("change", pedir);
    addEventListener("pointermove", (e) => {
      if (!dentro) { p.x = e.clientX; p.y = e.clientY; }     // la primera vez aparece justo bajo el puntero
      dentro = true; objetivo.x = e.clientX; objetivo.y = e.clientY; pedir();
    }, { passive: true });
    addEventListener("pointerdown", (e) => {
      if (reducido.matches) return;
      ondas.push({ x: e.clientX, y: e.clientY, t: performance.now() });
      dentro = true; objetivo.x = e.clientX; objetivo.y = e.clientY; pedir();
    }, { passive: true });
    // En táctil el "puntero" desaparece al levantar el dedo; con ratón, al salir de la ventana.
    addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") { dentro = false; pedir(); } }, { passive: true });
    document.documentElement.addEventListener("pointerleave", () => { dentro = false; pedir(); });
  })();

})();
