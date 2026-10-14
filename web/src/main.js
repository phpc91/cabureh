import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/source-serif-4/400.css';
import './tokens.css';
import './app.css';
import * as d3 from 'd3';
import { criarRuntime } from './runtime.js';
import { iniciar } from './app.js';

iniciar(criarRuntime(), d3);
