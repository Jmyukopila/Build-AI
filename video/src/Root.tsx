// Registro de composiciones de Remotion.
import React from 'react';
import {Composition} from 'remotion';
import {DURACION_TOTAL, Promo} from './Promo';
import {ALTO, ANCHO, FPS} from './tema';

export const Root: React.FC = () => (
	<Composition id="BuildAIPromo" component={Promo} durationInFrames={DURACION_TOTAL} fps={FPS} width={ANCHO} height={ALTO} />
);
