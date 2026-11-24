// Genera la narración con ElevenLabs: un MP3 por escena en public/voz/<id>.mp3
// y las duraciones en src/voz.json (las usa Promo.tsx para comprobar que cada frase cabe).
//
// Uso:  node --env-file=.env scripts/generar-voz.mjs [--forzar]
// .env: ELEVENLABS_API_KEY=...   (obligatoria)
//       ELEVENLABS_VOZ_ID=...    (opcional; por defecto "George", multilingüe)
import {execFileSync} from 'node:child_process';
import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..');
const clave = process.env.ELEVENLABS_API_KEY;
const vozId = process.env.ELEVENLABS_VOZ_ID || 'JBFqnCBsd6RMkjVDRZzb';
const modelo = 'eleven_multilingual_v2';
const forzar = process.argv.includes('--forzar');

if (!clave) {
	console.error('Falta ELEVENLABS_API_KEY en video/.env');
	process.exit(1);
}

const guion = JSON.parse(readFileSync(join(raiz, 'src', 'guion.json'), 'utf8'));
const carpeta = join(raiz, 'public', 'voz');
mkdirSync(carpeta, {recursive: true});

const duracion = (archivo) =>
	Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', archivo]).toString().trim());

const sintetizar = async (i, texto) => {
	const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${vozId}?output_format=mp3_44100_128`, {
		method: 'POST',
		headers: {'xi-api-key': clave, 'Content-Type': 'application/json'},
		body: JSON.stringify({
			text: texto,
			model_id: modelo,
			// El texto vecino da continuidad de entonación entre frases.
			previous_text: guion[i - 1]?.texto,
			next_text: guion[i + 1]?.texto,
			voice_settings: {stability: 0.5, similarity_boost: 0.8, style: 0.25, use_speaker_boost: true},
		}),
	});
	if (!r.ok) {
		const detalle = (await r.text()).slice(0, 300);
		const pista =
			r.status === 402
				? '\nLas voces de la Voice Library necesitan un plan de pago de ElevenLabs para usarse por API.'
				: '';
		throw new Error(`ElevenLabs respondió ${r.status}: ${detalle}${pista}`);
	}
	return Buffer.from(await r.arrayBuffer());
};

const principal = async () => {
	// Primero se generan todas las frases en memoria y luego se escriben:
	// si una falla, no quedan mezcladas voces distintas en public/voz/.
	const nuevos = [];
	for (const [i, {id, texto}] of guion.entries()) {
		const archivo = join(carpeta, `${id}.mp3`);
		if (forzar || !existsSync(archivo)) {
			nuevos.push([archivo, await sintetizar(i, texto)]);
			console.log(`generado  ${id}`);
		} else {
			console.log(`existente ${id} (usa --forzar para regenerar)`);
		}
	}
	for (const [archivo, datos] of nuevos) writeFileSync(archivo, datos);

	const duraciones = Object.fromEntries(guion.map(({id}) => [id, duracion(join(carpeta, `${id}.mp3`))]));
	writeFileSync(join(raiz, 'src', 'voz.json'), JSON.stringify(duraciones, null, '\t') + '\n');
	console.log(duraciones);
};

principal().catch((e) => {
	console.error(e.message);
	process.exitCode = 1;
});
