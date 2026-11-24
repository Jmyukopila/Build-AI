// Plantilla de capítulo: columna izquierda (progreso, número, título, frase)
// y ventana con la grabación real a la derecha.
import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {color, fuente} from '../tema';
import {Fondo} from './Fondo';
import {Revelar, Scramble} from './Texto';
import {Dato, Toma, Ventana} from './Ventana';

export type DatosCapitulo = {
	numero: number;
	total: number;
	titulo: [string, string];
	frase: string;
	inicioSeg: number;
	velocidad: number;
	tomas: Toma[];
	tituloVentana: string;
	dato?: {valor: string; detalle: string; inicio: number; mono?: boolean};
	pie: string;
};

const Progreso: React.FC<{numero: number; total: number}> = ({numero, total}) => {
	const frame = useCurrentFrame();
	return (
		<div style={{display: 'flex', gap: 8}}>
			{Array.from({length: total}).map((_, i) => {
				const actual = i === numero - 1;
				const hecho = i < numero - 1;
				const ancho = actual ? interpolate(frame, [4, 22], [0, 44], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 44;
				return (
					<div key={i} style={{width: 44, height: 4, borderRadius: 2, backgroundColor: 'rgba(181,172,255,0.16)'}}>
						<div
							style={{
								width: hecho || actual ? ancho : 0,
								height: 4,
								borderRadius: 2,
								backgroundColor: actual ? color.ambar : color.accion,
								boxShadow: actual ? '0 0 12px rgba(235,187,82,0.6)' : undefined,
							}}
						/>
					</div>
				);
			})}
		</div>
	);
};

export const Capitulo: React.FC<DatosCapitulo> = (d) => {
	const frame = useCurrentFrame();
	const pie = interpolate(frame, [20, 36], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill>
			<Fondo onda={0.85} base={760} />
			<div style={{position: 'absolute', left: 70, top: 360, width: 470}}>
				<Progreso numero={d.numero} total={d.total} />
				<div
					style={{
						marginTop: 26,
						fontFamily: fuente.mono,
						fontSize: 18,
						letterSpacing: '0.2em',
						color: color.tinta3,
					}}
				>
					{String(d.numero).padStart(2, '0')} / {String(d.total).padStart(2, '0')}
				</div>
				<div
					style={{
						marginTop: 10,
						fontFamily: fuente.sans,
						fontWeight: 700,
						fontSize: 52,
						lineHeight: 1.02,
						letterSpacing: '-0.01em',
						color: color.tinta,
						textTransform: 'uppercase',
					}}
				>
					<Scramble texto={d.titulo[0]} inicio={6} duracion={22} />
					<br />
					<Scramble texto={d.titulo[1]} inicio={12} duracion={24} style={{color: color.acento}} />
				</div>
				<div style={{marginTop: 26, fontFamily: fuente.sans, fontSize: 27, lineHeight: 1.35, color: color.tinta2}}>
					<Revelar texto={d.frase} inicio={30} porPalabra={2} />
				</div>
			</div>
			<Ventana
				x={560}
				y={138}
				ancho={1290}
				alto={726}
				inicioSeg={d.inicioSeg}
				velocidad={d.velocidad}
				tomas={d.tomas}
				titulo={d.tituloVentana}
			>
				{d.dato ? <Dato {...d.dato} /> : null}
			</Ventana>
			<div
				style={{
					position: 'absolute',
					left: 562,
					top: 924,
					fontFamily: fuente.mono,
					fontSize: 14,
					lineHeight: 1.7,
					letterSpacing: '0.16em',
					color: color.tinta3,
					opacity: pie,
				}}
			>
				<span style={{color: color.acento}}>BUILDAI 0.6.2</span> · IA LOCAL QWEN3.5-4B · DEMO GRABADA CON BLENDER, TAMBIÉN
				AUTOCAD, SKETCHUP Y REVIT
				<br />
				{d.pie}
			</div>
		</AbsoluteFill>
	);
};
