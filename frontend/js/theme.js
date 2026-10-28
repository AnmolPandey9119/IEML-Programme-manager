/* Light / dark theme. The first choice follows the device; after that the person's choice is remembered. */
import { acts } from './core.js';

const KEY = 'pm-theme';
const read = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
const write = (v) => { try { localStorage.setItem(KEY, v); } catch { /* private mode: still works for this visit */ } };
const device = () => (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

export const current = () => document.documentElement.dataset.theme || read() || device();
export function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t === 'dark' ? '#080f24' : '#f6f4ee');
}
applyTheme(read() || device());

// Follow the device only while the person has not chosen.
window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => { if (!read()) applyTheme(device()); });

acts({
  toggleTheme: () => { const next = current() === 'dark' ? 'light' : 'dark'; write(next); applyTheme(next); },
});