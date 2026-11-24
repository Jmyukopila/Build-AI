// Masteriza el audio del video renderizado: normaliza a −14 LUFS (estándar de YouTube,
// Instagram y web) con pico real de −1,5 dBTP, en dos pasadas de loudnorm.
// El video se copia tal cual (sin recodificar).
//
// Uso: node scripts/masterizar.mjs <entrada.mp4> <salida.mp4>
import {spawnSync} from 'node:child_process';

const [entrada, salida] = process.argv.slice(2);
if (!entrada || !salida) {
	console.error('Uso: node scripts/masterizar.mjs <entrada.mp4> <salida.mp4>');
	process.exit(1);
}

const OBJETIVO = 'I=-14:TP=-1.5:LRA=11';

const medicion = spawnSync('ffmpeg', ['-hide_banner', '-i', entrada, '-af', `loudnorm=${OBJETIVO}:print_format=json`, '-f', 'null', '-'], {
	encoding: 'utf8',
});
const json = medicion.stderr.slice(medicion.stderr.lastIndexOf('{'), medicion.stderr.lastIndexOf('}') + 1);
const m = JSON.parse(json);
console.log(`antes: ${m.input_i} LUFS, pico ${m.input_tp} dBTP`);

const filtro = `loudnorm=${OBJETIVO}:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true`;
const final = spawnSync(
	'ffmpeg',
	['-v', 'error', '-y', '-i', entrada, '-c:v', 'copy', '-af', filtro, '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', salida],
	{stdio: 'inherit'},
);
if (final.status !== 0) process.exit(final.status ?? 1);
console.log(`masterizado: ${salida}`);
