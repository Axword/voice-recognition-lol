import { render } from 'preact';
import './styles/tokens.css';
import './styles/fonts.css';
import './styles/base.css';
import './styles/app.css';
import { bootToken } from './lib/api';
import { connect, refreshAll } from './lib/state';
import { App } from './app';

bootToken();
void refreshAll();
connect();

const root = document.getElementById('app');
if (root) render(<App />, root);
