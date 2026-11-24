// Escena 2: la promesa, sobre el interior amueblado real generado en Blender.
import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, staticFile, useCurrentFrame} from 'remotion';
import {Fondo} from '../componentes/Fondo';
import {Etiqueta, Revelar, Scramble, useEntrada} from '../componentes/Texto';
import {color, fuente, FPS, GRABACION} from '../tema';

export const Gancho: React.FC = () => {
	const frame = useCurrentFrame();
	const zoom = interpolate(frame, [0, 150], [1.18, 1.3]);
	return (
		<AbsoluteFill>
			<Fondo onda={0} />
			{/* Interior real del modelo en Blender (segundo 120 de la grabación) */}
			<AbsoluteFill style={{opacity: 0.5, filter: 'blur(1.5px) saturate(0.7)'}}>
				<OffthreadVideo
					src={staticFile(GRABACION.archivo)}
					trimBefore={120 * FPS}
					playbackRate={0.6}
					muted
					style={{
						position: 'absolute',
						left: 260,
						top: -40,
						width: 1918,
						height: 1010,
						transform: `scale(${zoom})`,
						transformOrigin: '30% 60%',
					}}
				/>
			</AbsoluteFill>
			<AbsoluteFill
				style={{
					background:
						'linear-gradient(90deg, #0A0B0D 22%, rgba(10,11,13,0.82) 50%, rgba(10,11,13,0.35) 100%), linear-gradient(0deg, #0A0B0D 0%, transparent 30%)',
				}}
			/>
			<div style={{position: 'absolute', left: 120, top: 300, width: 980}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 30}}>
					<Img
						src={staticFile('icono-marca.png')}
						style={{
							width: 124,
							height: 124,
							borderRadius: 28,
							boxShadow: '0 0 50px rgba(110,95,230,0.55)',
							...useEntrada(0, 18),
						}}
					/>
					<div style={{fontFamily: fuente.sans, fontWeight: 700, fontSize: 128, lineHeight: 1, color: color.tinta}}>
						<Scramble texto="Build" inicio={4} duracion={20} semilla="g1" />
						<Scramble texto="AI" inicio={12} duracion={16} semilla="g2" style={{color: color.acento}} />
					</div>
				</div>
				<div style={{marginTop: 26, fontFamily: fuente.sans, fontWeight: 700, fontSize: 62, color: color.acento}}>
					<Revelar texto="Diseña con palabras." inicio={14} porPalabra={3} />
				</div>
				<div style={{marginTop: 30, fontFamily: fuente.sans, fontSize: 44, lineHeight: 1.3, color: color.tinta}}>
					<Revelar texto="Pides una casa en español." inicio={40} porPalabra={3} />
				</div>
				<div style={{fontFamily: fuente.sans, fontSize: 44, lineHeight: 1.3, color: color.ambar}}>
					<Revelar texto="La IA la construye en tu programa de preferencia." inicio={64} porPalabra={3} />
				</div>
			</div>
			<Etiqueta style={{position: 'absolute', left: 120, bottom: 90, ...useEntrada(84)}}>
				Interior real generado por BuildAI
			</Etiqueta>
		</AbsoluteFill>
	);
};
