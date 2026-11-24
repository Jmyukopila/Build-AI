# Video promocional de BuildAI (Remotion)

Video de 30 s (1920×1080, 30 fps) montado sobre la grabación real de la app
(`WhatsApp Video 2026-11-24 at 10.42.26 AM.mp4`): encargo → la IA planifica →
modela en tu programa → render → modelo editable, con intro, cierre, narración de ElevenLabs
y música original. La demo se grabó con Blender, pero los textos hablan de los cuatro programas.

```bash
npm install
npm run voz      # genera la narración (solo las frases que falten)
npm run musica   # sintetiza la música de fondo y el whoosh de transición
npm run studio   # editar y previsualizar en el navegador
npm run render   # genera out/buildai-promo.mp4
```

## Narración (ElevenLabs)

- Clave en `video/.env` (no se sube a git): `ELEVENLABS_API_KEY=...`.
  Opcional: `ELEVENLABS_VOZ_ID=...` para usar otra voz (por defecto "George", multilingüe).
  Las voces de la Voice Library solo funcionan por API con un plan de pago; con la cuenta
  gratuita se pueden generar en la web de ElevenLabs y guardar como `public/voz/<escena>.mp3`.
- El texto está en `src/guion.json`, una frase por escena. Tras cambiarlo o cambiar de voz:
  `npm run voz -- --forzar`.
- `scripts/generar-voz.mjs` guarda `public/voz/<escena>.mp3` y las duraciones en `src/voz.json`.
  `src/Promo.tsx` reparte los 30 s según lo que dura cada frase. Si la narración
  no cabe, el render falla y te dice cuántos frames sobran.

## Música

- `scripts/generar-musica.mjs` sintetiza desde cero (sin derechos de terceros) una pista de 30 s
  a 90 BPM: pads, bajo suave, arpegio tipo campana con eco y reverberación, resolviendo al final.
  Guarda `public/musica.mp3` y `public/whoosh.mp3`.
- En `src/Promo.tsx` la música baja de volumen mientras habla la voz (`volumenMusica`) y suena un
  whoosh en el centro de cada transición. Para usar otra pista, sustituye `public/musica.mp3`.

## Otros ajustes

- `public/grabacion.mp4` es la grabación recodificada (sin audio, keyframe cada 15 frames).
  Para regenerarla:
  `ffmpeg -i "WhatsApp Video 2026-11-24 at 10.42.26 AM.mp4" -an -c:v libx264 -crf 18 -g 15 -pix_fmt yuv420p -r 30 public/grabacion.mp4`
- Tramos de la grabación y encuadres de cámara de cada capítulo: `CAPITULOS` en `src/Promo.tsx`.
  `x`/`y` son píxeles de la grabación original (1918×1010); `p` es el momento de la escena (0–1).
  La velocidad de cada tramo se calcula sola para que encaje en su escena.
- El cierre muestra la portada de la web (`public/web-buildai.png`, captura de `website/index.html`
  en modo oscuro). Si la web cambia, vuelve a capturarla a 1440×900.
- Colores y fuente (Instrument Sans) salen de la marca: `src/tema.ts`.
- En git solo entra el video final `out/*.mp4`; el resto de `.mp4`, `node_modules/` y `.env` se ignoran (reglas en el `.gitignore` de la raíz).
