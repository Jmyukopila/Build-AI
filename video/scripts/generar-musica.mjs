// Música de fondo original (sin derechos de terceros) sintetizada desde cero:
// pads cálidos + bajo suave + arpegio tipo campana con eco + reverberación.
// 30 s a 90 BPM, progresión Sol – Re – Si m – La – Sol – Re (resuelve en Re al final).
// También genera un "whoosh" corto para las transiciones entre escenas.
//
// Uso: node scripts/generar-musica.mjs   →   public/musica.mp3, public/whoosh.mp3
import {execFileSync} from 'node:child_process';
import {mkdtempSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..');
const SR = 44100;
const DURACION = 30;
const N = SR * DURACION;
const TAU = Math.PI * 2;

const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
const BPM = 90;
const PULSO = 60 / BPM; // 0,667 s
const COMPAS = PULSO * 4; // 2,667 s

// Acordes de 2 compases: [bajo, notas del pad]
const ACORDES = [
	[43, [55, 59, 62, 66, 69]], // Sol maj9
	[38, [57, 62, 64, 66, 69]], // Re add9
	[47, [54, 57, 62, 64, 66]], // Si m7(11)
	[45, [52, 57, 62, 64, 69]], // La sus4
	[43, [55, 59, 62, 66, 71]], // Sol maj9 (más abierto)
	[38, [57, 62, 66, 69, 74]], // Re (resolución)
];
const DUR_ACORDE = COMPAS * 2;

const izq = new Float64Array(N);
const der = new Float64Array(N);
const envioI = new Float64Array(N); // envío a reverberación
const envioD = new Float64Array(N);

const suave = (x) => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, x)));

// ── Pads y bajo ────────────────────────────────────────────────────────────
ACORDES.forEach(([bajo, notas], i) => {
	const t0 = i * DUR_ACORDE;
	const ultimo = i === ACORDES.length - 1;
	const t1 = ultimo ? DURACION : t0 + DUR_ACORDE;
	const ataque = i === 0 ? 2.2 : 0.9;
	const caida = ultimo ? 0.01 : 1.4;
	const ini = Math.floor(t0 * SR);
	const fin = Math.min(N, Math.floor((t1 + caida) * SR));
	for (let s = ini; s < fin; s++) {
		const t = s / SR;
		const env = suave((t - t0) / ataque) * (t > t1 ? 1 - suave((t - t1) / caida) : 1);
		if (env <= 0) continue;
		// Brillo que crece a lo largo del video y respira lento (como un filtro que se abre).
		const brillo = 0.55 + 0.35 * (t / DURACION) + 0.1 * Math.sin(TAU * 0.11 * t);
		let l = 0;
		let r = 0;
		notas.forEach((m, k) => {
			const f = hz(m);
			for (const [desafino, lado] of [
				[-5, 0.8],
				[5, 0.2],
			]) {
				const fd = f * 2 ** (desafino / 1200);
				let v = 0;
				for (let h = 1; h <= 5; h++) v += (Math.sin(TAU * fd * h * t + k + h) * brillo ** (h - 1)) / h ** 1.7;
				l += v * lado;
				r += v * (1 - lado);
			}
		});
		const nivelPad = 0.035 * env;
		const sub = 0.11 * env * (Math.sin(TAU * hz(bajo) * t) + 0.18 * Math.sin(TAU * hz(bajo) * 2 * t));
		izq[s] += l * nivelPad + sub;
		der[s] += r * nivelPad + sub;
		envioI[s] += l * nivelPad * 0.9;
		envioD[s] += r * nivelPad * 0.9;
	}
});

// ── Arpegio tipo campana ───────────────────────────────────────────────────
const nota = (inicio, midi, vel, pan) => {
	const f = hz(midi);
	const ini = Math.floor(inicio * SR);
	const largo = Math.floor(1.6 * SR);
	for (let k = 0; k < largo && ini + k < N; k++) {
		const t = k / SR;
		const env = Math.min(1, t / 0.006) * Math.exp(-t / 0.38);
		const v = (Math.sin(TAU * f * t) + 0.28 * Math.sin(TAU * f * 2 * t) * Math.exp(-t / 0.12) + 0.08 * Math.sin(TAU * f * 3.01 * t) * Math.exp(-t / 0.06)) * env * vel;
		izq[ini + k] += v * (1 - pan);
		der[ini + k] += v * pan;
		envioI[ini + k] += v * (1 - pan) * 0.6;
		envioD[ini + k] += v * pan * 0.6;
	}
};
const PATRON = [0, 2, 1, 3, 2, 4, 3, 1];
const inicioArpegio = COMPAS; // entra en el compás 2
const finArpegio = (ACORDES.length - 1) * DUR_ACORDE;
for (let t = inicioArpegio, paso = 0; t < finArpegio - 0.01; t += PULSO / 2, paso++) {
	const acorde = ACORDES[Math.floor(t / DUR_ACORDE)][1];
	// Primero solo negras; a partir del segundo acorde, corcheas.
	const corcheas = t >= DUR_ACORDE;
	if (!corcheas && paso % 2 === 1) continue;
	const acento = paso % 4 === 0 ? 1 : 0.7;
	nota(t, acorde[PATRON[paso % PATRON.length]] + 12, 0.055 * acento, paso % 2 ? 0.35 : 0.65);
}
nota(finArpegio, 74 + 12, 0.07, 0.5); // campanada final en Re

// ── Eco ping-pong (corchea con puntillo) sobre todo el envío ──────────────
const ECO = Math.floor(PULSO * 0.75 * SR);
for (let s = ECO; s < N; s++) {
	envioI[s] += envioD[s - ECO] * 0.32;
	envioD[s] += envioI[s - ECO] * 0.32;
}

// ── Reverberación tipo Freeverb ─────────────────────────────────────────────
const reverb = (entrada, extra) => {
	const salida = new Float64Array(N);
	for (const d of [1116, 1188, 1277, 1356, 1422, 1491]) {
		const buf = new Float64Array(d + extra);
		let idx = 0;
		let filtro = 0;
		for (let s = 0; s < N; s++) {
			const y = buf[idx];
			filtro = y * 0.75 + filtro * 0.25;
			buf[idx] = entrada[s] + filtro * 0.86;
			salida[s] += y;
			idx = (idx + 1) % buf.length;
		}
	}
	for (const d of [556, 441, 341]) {
		const buf = new Float64Array(d + extra);
		let idx = 0;
		for (let s = 0; s < N; s++) {
			const b = buf[idx];
			const x = salida[s];
			buf[idx] = x + b * 0.5;
			salida[s] = b - x;
			idx = (idx + 1) % buf.length;
		}
	}
	return salida;
};
const revI = reverb(envioI, 0);
const revD = reverb(envioD, 23);

// ── Mezcla final ───────────────────────────────────────────────────────────
const mezcla = new Float32Array(N * 2);
let pico = 0;
for (let s = 0; s < N; s++) {
	const t = s / SR;
	const fundido = suave(t / 1.2) * (1 - suave((t - (DURACION - 2.5)) / 2.5));
	const l = Math.tanh((izq[s] + revI[s] * 0.09) * 1.2) * fundido;
	const r = Math.tanh((der[s] + revD[s] * 0.09) * 1.2) * fundido;
	mezcla[s * 2] = l;
	mezcla[s * 2 + 1] = r;
	pico = Math.max(pico, Math.abs(l), Math.abs(r));
}
for (let i = 0; i < mezcla.length; i++) mezcla[i] *= 0.7 / pico; // pico a −3 dBFS

// ── Whoosh: ruido filtrado con barrido, pico a los 0,45 s ──────────────────
const whoosh = () => {
	const largo = Math.floor(0.9 * SR);
	const datos = new Float32Array(largo * 2);
	let semilla = 7;
	const azar = () => ((semilla = (semilla * 16807) % 2147483647) / 2147483647) * 2 - 1;
	let bajo = [0, 0];
	let banda = [0, 0];
	for (let k = 0; k < largo; k++) {
		const t = k / SR;
		const env = t < 0.45 ? (t / 0.45) ** 2 : Math.exp(-(t - 0.45) / 0.12);
		const corte = 300 + 2600 * Math.sin(Math.PI * Math.min(1, t / 0.6));
		const f = 2 * Math.sin((Math.PI * corte) / SR);
		for (const c of [0, 1]) {
			const x = azar();
			bajo[c] += f * banda[c];
			const alto = x - bajo[c] - 0.7 * banda[c];
			banda[c] += f * alto;
			datos[k * 2 + c] = banda[c] * env * 0.5;
		}
	}
	let p = 0;
	for (const v of datos) p = Math.max(p, Math.abs(v));
	for (let i = 0; i < datos.length; i++) datos[i] *= 0.7 / p;
	return datos;
};

const wav = (muestras) => {
	const buf = Buffer.alloc(44 + muestras.length * 2);
	buf.write('RIFF', 0);
	buf.writeUInt32LE(36 + muestras.length * 2, 4);
	buf.write('WAVEfmt ', 8);
	buf.writeUInt32LE(16, 16);
	buf.writeUInt16LE(1, 20);
	buf.writeUInt16LE(2, 22);
	buf.writeUInt32LE(SR, 24);
	buf.writeUInt32LE(SR * 4, 28);
	buf.writeUInt16LE(4, 32);
	buf.writeUInt16LE(16, 34);
	buf.write('data', 36);
	buf.writeUInt32LE(muestras.length * 2, 40);
	for (let i = 0; i < muestras.length; i++) buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, muestras[i])) * 32767), 44 + i * 2);
	return buf;
};

const temporal = mkdtempSync(join(tmpdir(), 'buildai-musica-'));
try {
	for (const [nombre, datos] of [
		['musica', mezcla],
		['whoosh', whoosh()],
	]) {
		const origen = join(temporal, `${nombre}.wav`);
		writeFileSync(origen, wav(datos));
		execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', origen, '-b:a', '192k', join(raiz, 'public', `${nombre}.mp3`)]);
		console.log(`generado public/${nombre}.mp3`);
	}
} finally {
	rmSync(temporal, {recursive: true, force: true});
}
