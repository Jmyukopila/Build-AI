// Escena 1: presentación de la marca con texto que se resuelve.
import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {Fondo} from '../componentes/Fondo';
import {Etiqueta, Revelar, Scramble, useEntrada} from '../componentes/Texto';
import {color, fuente} from '../tema';

export const Intro: React.FC = () => {
	const frame = useCurrentFrame();
	const onda = interpolate(frame, [0, 30], [0, 1], {extrapolateRight: 'clamp'});
	const linea = interpolate(frame, [26, 50], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	return (
		<AbsoluteFill>
			<Fondo onda={onda} base={640} />
			<div style={{position: 'absolute', left: 120, top: 250}}>
				<Etiqueta style={useEntrada(2)}>Estudio de arquitectura con IA · 2026</Etiqueta>
				<div style={{marginTop: 22, fontFamily: fuente.sans, fontSize: 40, color: color.tinta2, ...useEntrada(4)}}>
					Presentamos
				</div>
				<div
					style={{
						fontFamily: fuente.sans,
						fontWeight: 700,
						fontSize: 210,
						lineHeight: 1,
						letterSpacing: '-0.03em',
						color: color.tinta,
					}}
				>
					<Scramble texto="Build" inicio={8} duracion={20} />
					<Scramble texto="AI" inicio={16} duracion={16} style={{color: color.acento}} />
				</div>
				<div
					style={{
						marginTop: 14,
						height: 6,
						width: 640 * linea,
						borderRadius: 3,
						background: `linear-gradient(90deg, ${color.accion}, ${color.acento} 60%, ${color.ambar})`,
						boxShadow: '0 0 24px rgba(110,95,230,0.6)',
					}}
				/>
				<div style={{marginTop: 30, fontFamily: fuente.sans, fontSize: 34, color: color.tinta2}}>
					<Revelar texto="Blender · AutoCAD · SketchUp · Revit" inicio={34} porPalabra={2} />
				</div>
			</div>
		</AbsoluteFill>
	);
};
