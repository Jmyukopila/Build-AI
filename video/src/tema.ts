// Tema visual del video: colores y fuentes tomados de la marca de BuildAI
// (buildai/ui/style.css y website/base.css, variante oscura).
import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const FPS = 30;
export const ANCHO = 1920;
export const ALTO = 1080;

export const color = {
	fondo: '#0A0B0D',
	hoja: '#1A1D1B',
	tinta: '#E9ECE5',
	tinta2: '#B3BBB2',
	tinta3: '#98A197',
	linea: '#2A2F2C',
	accion: '#6E5FE6',
	acento: '#B5ACFF',
	ambar: '#EBBB52',
	pino: '#72CD8D',
};

export const fuente = {
	sans: '"Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
	mono: '"Cascadia Mono", "Cascadia Code", Consolas, ui-monospace, monospace',
};

// Instrument Sans es la fuente de la web de BuildAI (variable 400–700).
loadFont({
	family: 'Instrument Sans',
	url: staticFile('instrument-sans-latin.woff2'),
	weight: '400 700',
});

// Datos reales de la grabación (video/WhatsApp Video 2026-11-24 ...mp4).
export const GRABACION = {
	archivo: 'grabacion.mp4',
	ancho: 1918,
	alto: 1010,
	duracion: 125.6,
};
