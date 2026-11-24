// Fondo común: retícula de plano arquitectónico + onda de puntos en perspectiva.
import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {color} from '../tema';

const COLUMNAS = 96;
const FILAS = 15;

const OndaPuntos: React.FC<{base: number; intensidad: number}> = ({base, intensidad}) => {
	const frame = useCurrentFrame();
	const fase = frame * 0.028;
	const puntos: React.ReactNode[] = [];
	for (let f = 0; f < FILAS; f++) {
		const prof = f / (FILAS - 1); // 0 = lejos, 1 = cerca
		for (let c = 0; c < COLUMNAS; c++) {
			const x = (c / (COLUMNAS - 1)) * 2140 - 110 + Math.sin(fase * 0.5 + f) * 8;
			const y =
				base +
				prof * 250 +
				Math.sin(x * 0.0055 + fase + f * 0.33) * (24 + prof * 46) +
				Math.sin(x * 0.012 - fase * 1.4) * 14;
			const brillo = 0.5 + 0.5 * Math.sin(x * 0.01 + fase * 2 + f);
			const r = 0.7 + prof * 1.9;
			const calido = (c * 7 + f * 13) % 29 === 0;
			puntos.push(
				<circle
					key={`${f}-${c}`}
					cx={x}
					cy={y}
					r={r}
					fill={calido ? color.ambar : f % 3 === 0 ? color.acento : color.accion}
					opacity={(0.08 + prof * 0.5 * brillo) * intensidad}
				/>,
			);
		}
	}
	return (
		<svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
			{puntos}
		</svg>
	);
};

export const Fondo: React.FC<{onda?: number; base?: number}> = ({onda = 1, base = 700}) => {
	const frame = useCurrentFrame();
	const deriva = interpolate(frame, [0, 600], [0, 64]);
	return (
		<AbsoluteFill style={{backgroundColor: color.fondo, overflow: 'hidden'}}>
			{/* Retícula de plano, desvanecida hacia los bordes */}
			<AbsoluteFill
				style={{
					backgroundImage:
						'linear-gradient(rgba(181,172,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(181,172,255,0.045) 1px, transparent 1px)',
					backgroundSize: '64px 64px',
					backgroundPosition: `${deriva}px ${deriva / 2}px`,
					maskImage: 'radial-gradient(ellipse 70% 65% at 50% 45%, black 20%, transparent 100%)',
				}}
			/>
			<AbsoluteFill
				style={{
					background:
						'radial-gradient(900px 600px at 12% 8%, rgba(110,95,230,0.16), transparent 70%), radial-gradient(700px 500px at 95% 100%, rgba(235,187,82,0.06), transparent 70%)',
				}}
			/>
			{onda > 0 ? <OndaPuntos base={base} intensidad={onda} /> : null}
			<AbsoluteFill
				style={{background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)'}}
			/>
		</AbsoluteFill>
	);
};
