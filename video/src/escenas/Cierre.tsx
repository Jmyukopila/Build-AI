// Escena final: los cuatro programas, ventajas y la portada de la web de BuildAI.
import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Fondo} from '../componentes/Fondo';
import {Etiqueta, Revelar, Scramble, useEntrada} from '../componentes/Texto';
import {color, fuente} from '../tema';

const PROGRAMAS = ['Blender', 'AutoCAD', 'SketchUp', 'Revit'];

const Programas: React.FC<{inicio: number}> = ({inicio}) => {
	const frame = useCurrentFrame();
	const separacion = 190;
	const linea = interpolate(frame, [inicio, inicio + 40], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.inOut(Easing.cubic),
	});
	return (
		<div style={{position: 'relative', height: 70, width: separacion * 3 + 40}}>
			<div
				style={{
					position: 'absolute',
					left: 10,
					top: 9,
					height: 2,
					width: separacion * 3 * linea,
					background: `linear-gradient(90deg, ${color.accion}, ${color.acento})`,
				}}
			/>
			{PROGRAMAS.map((p, i) => {
				const t = interpolate(frame, [inicio + i * 10, inicio + i * 10 + 12], [0, 1], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				});
				return (
					<div key={p} style={{position: 'absolute', left: i * separacion, top: 0, opacity: t}}>
						<div
							style={{
								width: 20,
								height: 20,
								borderRadius: 20,
								backgroundColor: color.accion,
								boxShadow: '0 0 18px rgba(110,95,230,0.8)',
								transform: `scale(${t})`,
							}}
						/>
						<div
							style={{
								marginTop: 14,
								fontFamily: fuente.mono,
								fontSize: 15,
								letterSpacing: '0.14em',
								textTransform: 'uppercase',
								color: color.tinta2,
							}}
						>
							{p}
						</div>
					</div>
				);
			})}
		</div>
	);
};

const Chip: React.FC<{texto: string; inicio: number; calido?: boolean}> = ({texto, inicio, calido}) => (
	<div
		style={{
			padding: '9px 18px',
			borderRadius: 999,
			border: `1.5px solid ${calido ? color.ambar : color.acento}`,
			backgroundColor: calido ? 'rgba(235,187,82,0.1)' : 'rgba(181,172,255,0.1)',
			fontFamily: fuente.sans,
			fontWeight: 600,
			fontSize: 21,
			color: color.tinta,
			...useEntrada(inicio, 10),
		}}
	>
		{texto}
	</div>
);

/** Portada de la web (captura de website/index.html en modo oscuro) en un marco de navegador. */
const PortadaWeb: React.FC<{ancho: number}> = ({ancho}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const alto = Math.round((ancho * 1350) / 2160);
	const zoom = interpolate(frame, [0, durationInFrames], [1.0, 1.08]);
	return (
		<div
			style={{
				width: ancho,
				borderRadius: 14,
				overflow: 'hidden',
				border: '1px solid rgba(181,172,255,0.4)',
				backgroundColor: '#101211',
				boxShadow: '0 0 0 1px rgba(110,95,230,0.15), 0 0 80px rgba(110,95,230,0.45), 0 30px 70px rgba(0,0,0,0.6)',
			}}
		>
			<div
				style={{
					height: 30,
					display: 'flex',
					alignItems: 'center',
					gap: 7,
					padding: '0 14px',
					borderBottom: '1px solid rgba(181,172,255,0.18)',
					background: 'linear-gradient(90deg, rgba(110,95,230,0.18), rgba(26,29,27,0.6))',
				}}
			>
				{[0, 1, 2].map((i) => (
					<span key={i} style={{width: 9, height: 9, borderRadius: 9, backgroundColor: 'rgba(233,236,229,0.25)'}} />
				))}
			</div>
			<div style={{width: ancho, height: alto, overflow: 'hidden'}}>
				<Img
					src={staticFile('web-buildai.png')}
					style={{width: ancho, height: alto, transform: `scale(${zoom})`, transformOrigin: '50% 30%'}}
				/>
			</div>
		</div>
	);
};

export const Cierre: React.FC = () => {
	const frame = useCurrentFrame();
	const {fps, durationInFrames} = useVideoConfig();
	const tarjeta = spring({frame: frame - 12, fps, config: {damping: 18, stiffness: 110}});
	const salida = interpolate(frame, [durationInFrames - 18, durationInFrames], [1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	return (
		<AbsoluteFill style={{opacity: salida, backgroundColor: '#000'}}>
			<Fondo onda={0.6} base={820} />
			<div style={{position: 'absolute', left: 120, top: 200, width: 900}}>
				<Etiqueta style={useEntrada(0)}>Tu estudio, conectado</Etiqueta>
				<div style={{marginTop: 16, fontFamily: fuente.sans, fontWeight: 700, fontSize: 62, lineHeight: 1.08}}>
					<Scramble texto="Cuatro programas." inicio={4} duracion={22} style={{color: color.tinta}} />
					<br />
					<Scramble texto="Una sola conversación." inicio={12} duracion={26} style={{color: color.acento}} />
				</div>
				<div style={{marginTop: 46}}>
					<Programas inicio={26} />
				</div>
				<div style={{marginTop: 44, display: 'flex', gap: 14}}>
					<Chip texto="IA local incluida" inicio={66} />
					<Chip texto="Sin código" inicio={72} />
					<Chip texto="En español" inicio={78} calido />
				</div>
				<div style={{marginTop: 40, fontFamily: fuente.sans, fontSize: 40, lineHeight: 1.2, color: color.tinta}}>
					<Revelar texto="El próximo proyecto empieza" inicio={92} porPalabra={3} />
				</div>
				<div style={{fontFamily: fuente.sans, fontWeight: 700, fontSize: 52, lineHeight: 1.2, color: color.acento}}>
					<Revelar texto="con una frase." inicio={106} porPalabra={4} />
				</div>
			</div>
			<div
				style={{
					position: 'absolute',
					right: 110,
					top: 230,
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					opacity: Math.min(1, Math.max(0, tarjeta)),
					transform: `translateY(${(1 - tarjeta) * 40}px)`,
				}}
			>
				<PortadaWeb ancho={680} />
				<div style={{marginTop: 34, display: 'flex', alignItems: 'center', gap: 14}}>
					<Img src={staticFile('icono-marca.png')} style={{width: 54, height: 54, borderRadius: 13}} />
					<div style={{fontFamily: fuente.sans, fontWeight: 700, fontSize: 46, color: color.tinta}}>
						Build<span style={{color: color.acento}}>AI</span>
					</div>
				</div>
				<Etiqueta style={{marginTop: 12, fontSize: 13}}>Descarga para Windows · v0.6.2</Etiqueta>
			</div>
		</AbsoluteFill>
	);
};
