(() => {
  const system = matchMedia('(prefers-color-scheme: dark)');
  let preference = 'system';
  try { preference = localStorage.getItem('radar-theme') || 'system'; } catch (_) {}
  if (!['system', 'light', 'dark'].includes(preference)) preference = 'system';
  function apply() {
    document.documentElement.dataset.theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
    document.documentElement.style.colorScheme = document.documentElement.dataset.theme;
    document.getElementById('theme-color')?.setAttribute('content', document.documentElement.dataset.theme === 'dark' ? '#0d0f12' : '#f4f5f7');
    document.querySelectorAll('[data-theme-select]').forEach(el => { el.value = preference; });
    window.dispatchEvent(new Event('themechange'));
  }
  apply();
  system.addEventListener('change', apply);
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    document.querySelectorAll('[data-theme-select]').forEach(el => el.addEventListener('change', () => {
      preference = el.value;
      try { localStorage.setItem('radar-theme', preference); } catch (_) {}
      apply();
    }));
  });
})();
