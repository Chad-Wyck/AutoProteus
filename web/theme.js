'use strict';
(() => {
  function apply(theme) {
    theme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="color-scheme"]').content = theme;
    const button = document.getElementById('theme-toggle');
    if (button) {
      const target = theme === 'dark' ? 'light' : 'dark';
      button.querySelector('.theme-icon').textContent = target === 'light' ? '☀' : '☾';
      button.querySelector('.theme-label').textContent = target === 'light' ? 'Light mode' : 'Dark mode';
      button.setAttribute('aria-label', 'Switch to ' + target + ' mode');
      button.title = 'Switch to ' + target + ' mode';
    }
    return theme;
  }
  let saved = 'dark';
  try { saved = localStorage.getItem('autoproteus-theme') || 'dark'; } catch (_) {}
  // Runs before the stylesheet so a saved light preference never flashes dark.
  apply(saved);
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.theme);
    document.getElementById('theme-toggle').addEventListener('click', () => {
      const theme = apply(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
      try { localStorage.setItem('autoproteus-theme', theme); } catch (_) {}
    });
  });
})();
