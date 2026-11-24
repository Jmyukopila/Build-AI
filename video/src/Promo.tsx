// Composición principal (30 s): intro → promesa → 5 capítulos con la grabación real → cierre,
// narrada con ElevenLabs. La duración de cada escena sale de lo que dura su frase
// (src/voz.json, generado por scripts/generar-voz.mjs) y el sobrante se reparte
// hasta llegar exactamente a DURACION_OBJETIVO.
// Tramos y coordenadas de cámara: video/WhatsApp Video 2026-11-24 at 10.42.26 AM.mp4 (1918×1010).
import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {linearTiming, TransitionSeries} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {Capitulo, DatosCapitulo} from './componentes/Capitulo';
import {Toma} from './componentes/Ventana';
import {Cierre} from './escenas/Cierre';
import {Gancho} from './escenas/Gancho';
import {Intro} from './escenas/Intro';
import {color, fuente, FPS} from './tema';
import voz from './voz.json';

export const DURACION_OBJETIVO = 30 * FPS;
const TRANSICION = 8;
/** Frames tras el inicio de la escena en que entra la voz. */
const ENTRADA_VOZ = 4;
/** Silencio mínimo entre una frase y la siguiente. */
const RESPIRO = 6;
/** Margen tras la última frase antes de acabar el video. */
const COLA = 16;

type IdVoz = keyof typeof voz;
const framesVoz = (id: IdVoz) => Math.ceil(voz[id] * FPS);

/** Tomas de cámara con el tiempo expresado como fracción (0–1) de la escena. */
type TomaRelativa = Omit<Toma, 'f'> & {p: number};

type Tramo = Omit<DatosCapitulo, 'velocidad' | 'tomas' | 'dato'> & {
	id: IdVoz;
	finSeg: number;
	tomas: TomaRelativa[];
	dato?: Omit<NonNullable<DatosCapitulo['dato']>, 'inicio'> & {p: number};
};

const TOTAL = 5;

const CAPITULOS: Tramo[] = [
	{
		id: 'c1',
		numero: 1,
		total: TOTAL,
		titulo: ['Pídelo', 'en español'],
		frase: 'Escribes lo que quieres, como se lo dirías a un colega.',
		inicioSeg: 0.5,
		finSeg: 11.5,
		tituloVentana: 'Nueva conversación',
		tomas: [
			{p: 0, x: 1170, y: 640, z: 1.35},
			{p: 0.45, x: 1170, y: 860, z: 1.9},
			{p: 1, x: 1170, y: 860, z: 1.9},
		],
		pie: '“CRÉAME UNA CASA AMUEBLADA CON 2 HABITACIONES”',
	},
	{
		id: 'c2',
		numero: 2,
		total: TOTAL,
		titulo: ['Piensa', 'y planifica'],
		frase: 'Revisa la escena, decide medidas y reparte los espacios.',
		inicioSeg: 12,
		finSeg: 50,
		tituloVentana: 'Recibir · Pensar · Actuar · Entregar',
		tomas: [
			{p: 0, x: 1170, y: 600, z: 1.45},
			{p: 1, x: 1170, y: 460, z: 1.55},
		],
		dato: {valor: '8 × 6 m', detalle: '2 habitaciones · muros, forjado y cubierta · amueblado', p: 0.45},
		pie: 'LA IA CONSULTA EL ESTADO REAL DEL PROGRAMA ANTES DE TOCAR NADA',
	},
	{
		id: 'c3',
		numero: 3,
		total: TOTAL,
		titulo: ['Construye', 'en tu programa'],
		frase: 'Modela la casa en tu programa de preferencia, paso a paso.',
		inicioSeg: 50,
		finSeg: 93,
		tituloVentana: 'Actuar',
		tomas: [
			{p: 0, x: 1170, y: 460, z: 1.5},
			{p: 1, x: 1170, y: 560, z: 1.6},
		],
		dato: {valor: 'Salón + dormitorio', detalle: '7,6 × 5,4 m y 4,6 × 5,2 m, con puerta y ventanas', p: 0.4},
		pie: 'CADA HERRAMIENTA QUE USA LA IA QUEDA VISIBLE EN LA CONVERSACIÓN',
	},
	{
		id: 'c4',
		numero: 4,
		total: TOTAL,
		titulo: ['Render', 'fotorrealista'],
		frase: 'Configura cámara y luz de atardecer, y te entrega la imagen.',
		inicioSeg: 93,
		finSeg: 109.5,
		tituloVentana: 'Render fotorrealista',
		tomas: [
			{p: 0, x: 1060, y: 420, z: 1.75},
			{p: 0.5, x: 1060, y: 420, z: 1.75},
			{p: 1, x: 1120, y: 560, z: 1.45},
		],
		dato: {valor: '1 min 21 s', detalle: 'del encargo al primer render, con la IA local incluida', p: 0.25},
		pie: 'TIEMPO MEDIDO POR LA PROPIA APP EN ESTA GRABACIÓN',
	},
	{
		id: 'c5',
		numero: 5,
		total: TOTAL,
		titulo: ['Tu modelo,', 'editable'],
		frase: 'Todo queda en tu programa: la casa, los muebles y la escena.',
		inicioSeg: 113,
		finSeg: 125.3,
		tituloVentana: 'Escena generada',
		tomas: [
			{p: 0, x: 720, y: 470, z: 1.2},
			{p: 1, x: 640, y: 520, z: 1.45},
		],
		dato: {valor: '2 habitaciones', detalle: 'salón y dormitorio amueblados, como objetos editables', p: 0.5},
		pie: 'SIN RETOQUES: LO QUE VES ES LO QUE LA IA CONSTRUYÓ',
	},
];

// ── Duraciones a partir de la voz ──────────────────────────────────────────
// Entre escenas hay un solape de TRANSICION frames; cada frase debe terminar
// (más un respiro) antes de que empiece la siguiente.
// Como todas las frases entran ENTRADA_VOZ frames tras el inicio de su escena, basta con:
const minimo = (id: IdVoz) => framesVoz(id) + RESPIRO + TRANSICION;
const ORDEN: IdVoz[] = ['intro', 'gancho', ...CAPITULOS.map((c) => c.id), 'cierre'];
const base: Record<string, number> = Object.fromEntries(ORDEN.map((id) => [id, minimo(id)]));
base.cierre = ENTRADA_VOZ + framesVoz('cierre') + COLA;

const sobrante = DURACION_OBJETIVO + (ORDEN.length - 1) * TRANSICION - ORDEN.reduce((s, id) => s + base[id], 0);
if (sobrante < 0) {
	throw new Error(
		`La narración no cabe en ${DURACION_OBJETIVO / FPS} s: sobran ${-sobrante} frames. Acorta src/guion.json y regenera la voz.`,
	);
}
// El sobrante va a la promesa y a los capítulos, donde se ve la app.
const receptores: IdVoz[] = ['gancho', ...CAPITULOS.map((c) => c.id)];
receptores.forEach((id, i) => {
	base[id] += Math.floor(sobrante / receptores.length) + (i < sobrante % receptores.length ? 1 : 0);
});
const DURACION = base as Record<IdVoz, number>;

export const DURACION_TOTAL = ORDEN.reduce((s, id) => s + DURACION[id], 0) - (ORDEN.length - 1) * TRANSICION;

// ── Audio: música con "ducking" bajo la voz y whoosh en cada transición ─────
/** Frame absoluto en que empieza cada escena (las transiciones solapan escenas). */
const INICIOS = ORDEN.reduce<number[]>((acc, id, i) => [...acc, i === 0 ? 0 : acc[i - 1] + DURACION[ORDEN[i - 1]] - TRANSICION], []);
const TRAMOS_VOZ = ORDEN.map((id, i) => [INICIOS[i] + ENTRADA_VOZ, INICIOS[i] + ENTRADA_VOZ + framesVoz(id)] as const);
// Voz ≈ −23 LUFS y música ≈ −13,6 LUFS: así la música queda ~13 dB bajo la voz y nunca la supera.
const MUSICA_SOLA = 0.2;
const MUSICA_BAJO_VOZ = 0.075;
const RAMPA = 8;
const volumenMusica = (f: number) => {
	// Distancia (en frames) al tramo de voz más cercano: 0 dentro de una frase.
	const distancia = Math.min(...TRAMOS_VOZ.map(([a, b]) => (f < a ? a - f : f > b ? f - b : 0)));
	const t = Math.min(1, distancia / RAMPA);
	return MUSICA_BAJO_VOZ + (MUSICA_SOLA - MUSICA_BAJO_VOZ) * t;
};
/** El pico del whoosh (0,45 s) cae en el centro de cada transición. */
const PICO_WHOOSH = Math.round(0.45 * FPS);
const WHOOSHES = INICIOS.slice(1).map((inicio) => inicio + TRANSICION / 2 - PICO_WHOOSH);

const datosCapitulo = (t: Tramo): DatosCapitulo => {
	const d = DURACION[t.id];
	return {
		...t,
		velocidad: ((t.finSeg - t.inicioSeg) * FPS) / d,
		tomas: t.tomas.map(({p, ...r}) => ({...r, f: Math.round(p * (d - 1))})),
		dato: t.dato ? {...t.dato, inicio: Math.round(t.dato.p * d)} : undefined,
	};
};

// TransitionSeries solo acepta sus propios elementos como hijos: se devuelve el elemento, no un componente.
const transicion = (clave: string) => (
	<TransitionSeries.Transition key={clave} presentation={fade()} timing={linearTiming({durationInFrames: TRANSICION})} />
);

const escena = (id: IdVoz, contenido: React.ReactNode) => (
	<TransitionSeries.Sequence key={id} durationInFrames={DURACION[id]}>
		{contenido}
		<Sequence from={ENTRADA_VOZ} layout="none">
			<Audio src={staticFile(`voz/${id}.mp3`)} />
		</Sequence>
	</TransitionSeries.Sequence>
);

export const Promo: React.FC = () => (
	<AbsoluteFill style={{backgroundColor: color.fondo}}>
		<TransitionSeries>
			{escena('intro', <Intro />)}
			{transicion('t-gancho')}
			{escena('gancho', <Gancho />)}
			{CAPITULOS.flatMap((c) => [transicion(`t-${c.id}`), escena(c.id, <Capitulo {...datosCapitulo(c)} />)])}
			{transicion('t-cierre')}
			{escena('cierre', <Cierre />)}
		</TransitionSeries>
		{/* Música original sintetizada por scripts/generar-musica.mjs */}
		<Audio src={staticFile('musica.mp3')} volume={volumenMusica} />
		{WHOOSHES.map((desde) => (
			<Sequence key={desde} from={desde} durationInFrames={Math.round(0.9 * FPS)} layout="none">
				<Audio src={staticFile('whoosh.mp3')} volume={0.12} />
			</Sequence>
		))}
		<div
			style={{
				position: 'absolute',
				right: 40,
				bottom: 26,
				fontFamily: fuente.mono,
				fontSize: 11,
				letterSpacing: '0.2em',
				color: color.tinta3,
				opacity: 0.45,
			}}
		>
			GRABACIÓN REAL DE BUILDAI · VOZ GENERADA CON IA (ELEVENLABS) · VIDEO HECHO CON REMOTION
		</div>
	</AbsoluteFill>
);
