// Marco con brillo que muestra la grabación real de BuildAI, con una "cámara"
// que encuadra y hace zoom sobre zonas concretas (coordenadas en píxeles del original).
import React from 'react';
import {Easing, interpolate, OffthreadVideo, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {color, fuente, FPS, GRABACION} from '../tema';

export type Toma = {
	/** frame de la escena */
	f: number;
	/** punto de la grabación (px del original) que queda centrado */
	x: number;
	y: number;
	/** zoom relativo a "ajustar al ancho" */
	z: number;
};

const valorEn = (tomas: Toma[], frame: number, clave: 'x' | 'y' | 'z') => {
	if (tomas.length === 1) return tomas[0][clave];
	return interpolate(
		frame,
		tomas.map((t) => t.f),
		tomas.map((t) => t[clave]),
		{extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)},
	);
};

const Camara: React.FC<{
	ancho: number;
	alto: number;
	inicioSeg: number;
	velocidad: number;
	tomas: Toma[];
}> = ({ancho, alto, inicioSeg, velocidad, tomas}) => {
	const frame = useCurrentFrame();
	const base = ancho / GRABACION.ancho;
	const escala = base * valorEn(tomas, frame, 'z');
	const anchoV = GRABACION.ancho * escala;
	const altoV = GRABACION.alto * escala;
	const limitar = (v: number, min: number, max: number) => (min > max ? (min + max) / 2 : Math.min(max, Math.max(min, v)));
	const izq = limitar(ancho / 2 - valorEn(tomas, frame, 'x') * escala, ancho - anchoV, 0);
	const arr = limitar(alto / 2 - valorEn(tomas, frame, 'y') * escala, alto - altoV, 0);
	return (
		<div style={{position: 'absolute', inset: 0, overflow: 'hidden', backgroundColor: '#111312'}}>
			<div
				style={{
					position: 'absolute',
					left: 0,
					top: 0,
					width: GRABACION.ancho,
					height: GRABACION.alto,
					transformOrigin: '0 0',
					transform: `translate(${izq}px, ${arr}px) scale(${escala})`,
				}}
			>
				<OffthreadVideo
					src={staticFile(GRABACION.archivo)}
					trimBefore={Math.round(inicioSeg * FPS)}
					playbackRate={velocidad}
					muted
					style={{width: GRABACION.ancho, height: GRABACION.alto}}
				/>
			</div>
		</div>
	);
};

export const Ventana: React.FC<{
	x: number;
	y: number;
	ancho: number;
	alto: number;
	inicioSeg: number;
	velocidad: number;
	tomas: Toma[];
	titulo: string;
	children?: React.ReactNode;
}> = ({x, y, ancho, alto, inicioSeg, velocidad, tomas, titulo, children}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const s = spring({frame, fps, config: {damping: 200}, durationInFrames: 24});
	const pulso = 0.28 + 0.08 * Math.sin(frame / 18);
	const barra = 38;
	return (
		<div
			style={{
				position: 'absolute',
				left: x,
				top: y,
				width: ancho,
				height: alto + barra,
				borderRadius: 16,
				overflow: 'hidden',
				border: '1px solid rgba(181,172,255,0.38)',
				backgroundColor: '#0E100F',
				boxShadow: `0 0 0 1px rgba(110,95,230,0.15), 0 0 70px rgba(110,95,230,${pulso}), 0 30px 80px rgba(0,0,0,0.6)`,
				opacity: s,
				transform: `translateY(${(1 - s) * 30}px) scale(${0.97 + s * 0.03})`,
			}}
		>
			<div
				style={{
					height: barra,
					display: 'flex',
					alignItems: 'center',
					gap: 14,
					padding: '0 16px',
					borderBottom: '1px solid rgba(181,172,255,0.18)',
					background: 'linear-gradient(90deg, rgba(110,95,230,0.18), rgba(26,29,27,0.6))',
					fontFamily: fuente.mono,
					fontSize: 14,
					color: color.tinta2,
					letterSpacing: '0.06em',
				}}
			>
				<span style={{display: 'flex', alignItems: 'center', gap: 8, color: color.tinta}}>
					<span
						style={{
							width: 9,
							height: 9,
							borderRadius: 9,
							backgroundColor: '#F2525F',
							opacity: 0.55 + 0.45 * Math.abs(Math.sin(frame / 10)),
						}}
					/>
					GRABACIÓN REAL
				</span>
				<span style={{opacity: 0.5}}>|</span>
				<span>{titulo}</span>
				<span style={{marginLeft: 'auto', color: velocidad > 1 ? color.ambar : color.tinta3}}>
					{velocidad > 1 ? `ACELERADO ×${velocidad.toLocaleString('es', {maximumFractionDigits: velocidad >= 10 ? 0 : 1})}` : 'TIEMPO REAL'}
				</span>
			</div>
			<div style={{position: 'relative', width: ancho, height: alto}}>
				<Camara ancho={ancho} alto={alto} inicioSeg={inicioSeg} velocidad={velocidad} tomas={tomas} />
				{children}
			</div>
		</div>
	);
};

/** Dato destacado sobre la grabación (como el "0.76 px" de la referencia). */
export const Dato: React.FC<{valor: string; detalle: string; inicio: number; mono?: boolean}> = ({
	valor,
	detalle,
	inicio,
	mono,
}) => {
	const frame = useCurrentFrame();
	const t = interpolate(frame, [inicio, inicio + 16], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	return (
		<div
			style={{
				position: 'absolute',
				left: 0,
				right: 0,
				bottom: 0,
				padding: '90px 36px 26px',
				background: 'linear-gradient(to top, rgba(8,9,10,0.92) 30%, rgba(8,9,10,0))',
				opacity: t,
			}}
		>
			<div
				style={{
					fontFamily: mono ? fuente.mono : fuente.sans,
					fontWeight: 700,
					fontSize: mono ? 48 : 76,
					lineHeight: 1,
					color: color.ambar,
					transform: `translateY(${(1 - t) * 20}px)`,
					textShadow: '0 0 30px rgba(235,187,82,0.35)',
				}}
			>
				{valor}
			</div>
			<div style={{marginTop: 10, fontFamily: fuente.sans, fontSize: 22, color: color.tinta2}}>{detalle}</div>
		</div>
	);
};
