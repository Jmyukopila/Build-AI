// Efectos de texto: "scramble" (caracteres que se resuelven) y revelado por palabras.
import React from 'react';
import {Easing, interpolate, random, useCurrentFrame} from 'remotion';
import {color} from '../tema';

const MAYUSCULAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&$';
const MINUSCULAS = 'abcdefghijklmnopqrstuvwxyz0123456789#%&$';

export const Scramble: React.FC<{
	texto: string;
	inicio: number;
	duracion?: number;
	semilla?: string;
	style?: React.CSSProperties;
}> = ({texto, inicio, duracion = 24, semilla = texto, style}) => {
	const frame = useCurrentFrame();
	const letras = [...texto];
	const n = letras.length;
	return (
		<span style={style}>
			{letras.map((ch, i) => {
				if (ch === ' ' || ch === '\n') return ch;
				const aparece = inicio + (i / n) * duracion * 0.45;
				const resuelve = inicio + duracion * 0.35 + ((i + 1) / n) * duracion * 0.65;
				if (frame < aparece) {
					return (
						<span key={i} style={{opacity: 0}}>
							{ch}
						</span>
					);
				}
				if (frame >= resuelve) return <span key={i}>{ch}</span>;
				const juego = ch === ch.toLowerCase() && ch !== ch.toUpperCase() ? MINUSCULAS : MAYUSCULAS;
				const r = random(`${semilla}-${i}-${Math.floor(frame / 2)}`);
				return (
					<span key={i} style={{color: color.ambar, opacity: 0.9}}>
						{juego[Math.floor(r * juego.length)]}
					</span>
				);
			})}
		</span>
	);
};

export const Revelar: React.FC<{
	texto: string;
	inicio: number;
	porPalabra?: number;
	style?: React.CSSProperties;
}> = ({texto, inicio, porPalabra = 3, style}) => {
	const frame = useCurrentFrame();
	const palabras = texto.split(' ');
	return (
		<span style={style}>
			{palabras.map((p, i) => {
				const t = interpolate(frame, [inicio + i * porPalabra, inicio + i * porPalabra + 12], [0, 1], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
					easing: Easing.out(Easing.cubic),
				});
				return (
					<React.Fragment key={i}>
						<span
							style={{
								display: 'inline-block',
								opacity: t,
								transform: `translateY(${(1 - t) * 16}px)`,
								filter: `blur(${(1 - t) * 6}px)`,
							}}
						>
							{p}
						</span>
						{i < palabras.length - 1 ? ' ' : null}
					</React.Fragment>
				);
			})}
		</span>
	);
};

// Aparición simple (opacidad + subida) para bloques.
export const useEntrada = (inicio: number, duracion = 14) => {
	const frame = useCurrentFrame();
	const t = interpolate(frame, [inicio, inicio + duracion], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.out(Easing.cubic),
	});
	return {opacity: t, transform: `translateY(${(1 - t) * 18}px)`};
};

export const Etiqueta: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
	<div
		style={{
			fontFamily: '"Cascadia Mono", Consolas, monospace',
			fontSize: 15,
			letterSpacing: '0.22em',
			textTransform: 'uppercase',
			color: color.tinta3,
			...style,
		}}
	>
		{children}
	</div>
);
