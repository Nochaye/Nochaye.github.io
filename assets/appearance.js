import {readLocal, writeLocal} from './common.js';
const defaultColor = '#f6f7f3';
const picker = document.querySelector('#background-color');
const panel = document.querySelector('.appearance');
function applyBackground(color, persist = false) {
  if (typeof color !== 'string' || !/^#[0-9a-f]{6}$/i.test(color)) color = defaultColor;
  const channels = color.slice(1).match(/../g).map(c => {
    const v = parseInt(c, 16) / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  const luminance = channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  const dark = luminance < 0.179;
  const style = document.documentElement.style;
  style.setProperty('--bg', color);
  // Choose black or white to keep text on even saturated custom backgrounds readable.
  style.setProperty('--canvas-ink', dark ? '#ffffff' : '#000000');
  style.setProperty('--canvas-muted', dark ? '#ffffff' : '#000000');
  picker.value = color;
  document.querySelectorAll('[data-bg]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.bg === color.toLowerCase()));
  });
  if (persist) {
    const saved = writeLocal('starcape-background', color);
    document.querySelector('#appearance-status').textContent = saved
      ? '已保存，下次打开会沿用此背景。'
      : '浏览器禁止保存，背景仅在当前页面生效。';
  }
}
applyBackground(readLocal('starcape-background', defaultColor));
document.querySelectorAll('[data-bg]').forEach(button => {
  button.style.setProperty('--swatch', button.dataset.bg);
  button.addEventListener('click', () => applyBackground(button.dataset.bg, true));
});
picker.addEventListener('input', () => applyBackground(picker.value, true));
document.querySelector('#reset-background').addEventListener('click', () => applyBackground(defaultColor, true));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && panel.open) {
    panel.open = false;
    panel.querySelector('summary').focus();
  }
});
document.addEventListener('click', event => {
  if (panel.open && !panel.contains(event.target)) panel.open = false;
});
window.addEventListener('storage', event => {
  if (event.key === 'starcape-background' || event.key === null) {
    applyBackground(readLocal('starcape-background', defaultColor));
  }
});
