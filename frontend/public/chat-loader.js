/**
 * PASS24 AI-chat widget loader.
 *
 * Встраиваемый скрипт для сторонних сайтов PASS24. Добавляет плавающую
 * кнопку AI-помощника в правый нижний угол, открывает чат в iframe с
 * https://support.pass24pro.ru/chat-widget.
 *
 * Использование на сайте клиента — одна строка перед </body>:
 *   <script src="https://support.pass24pro.ru/chat-loader.js" async></script>
 *
 * Никаких изменений бэкенда / CORS не требуется: все запросы AI и
 * создания заявок идут из iframe в домен support.pass24pro.ru (same-origin).
 *
 * Опциональные data-атрибуты на теге <script>:
 *   data-host     — переопределить хост виджета (default: origin у script.src)
 *   data-z-index  — z-index кнопки и iframe (default: 2147483000)
 */
(function () {
  'use strict';

  if (window.__pass24ChatLoaded) return;
  window.__pass24ChatLoaded = true;

  // --- Конфигурация ---------------------------------------------------------
  var currentScript = document.currentScript || (function () {
    var scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();

  var scriptSrc = (currentScript && currentScript.src) || '';
  var defaultHost = scriptSrc ? new URL(scriptSrc).origin : 'https://support.pass24pro.ru';
  var host = (currentScript && currentScript.dataset.host) || defaultHost;
  var zIndex = parseInt((currentScript && currentScript.dataset.zIndex) || '2147483000', 10);
  var widgetUrl = host.replace(/\/$/, '') + '/chat-widget';

  // --- Стили (инжектируются один раз) ---------------------------------------
  var styleId = 'pass24-chat-loader-style';
  if (!document.getElementById(styleId)) {
    var style = document.createElement('style');
    style.id = styleId;
    // textContent на элементе <style> — безопасно, это не парсится как HTML.
    style.textContent = [
      '.pass24-chat-btn{position:fixed;right:24px;bottom:24px;width:60px;height:60px;border-radius:50%;',
      'background:#0f172a;color:#fff;border:0;cursor:pointer;box-shadow:0 10px 30px -6px rgba(15,23,42,0.4);',
      'display:flex;align-items:center;justify-content:center;transition:transform 0.15s,background 0.15s;',
      'font-family:-apple-system,BlinkMacSystemFont,sans-serif;}',
      '.pass24-chat-btn:hover{transform:scale(1.05);background:#1e293b;}',
      '.pass24-chat-btn:focus{outline:2px solid #6366f1;outline-offset:3px;}',
      '.pass24-chat-frame{position:fixed;right:16px;bottom:100px;width:400px;max-width:calc(100vw - 32px);',
      'height:620px;max-height:calc(100vh - 120px);border:0;border-radius:20px;background:transparent;',
      'box-shadow:0 24px 48px -12px rgba(15,23,42,0.25);display:none;color-scheme:light;}',
      '.pass24-chat-frame.is-open{display:block;}',
      '@media (max-width:480px){.pass24-chat-frame{right:0;left:0;bottom:0;width:100%;max-width:100%;',
      'height:85vh;max-height:85vh;border-radius:20px 20px 0 0;}}',
    ].join('');
    document.head.appendChild(style);
  }

  // --- SVG-иконки (через DOM API, без innerHTML) ----------------------------
  var SVG_NS = 'http://www.w3.org/2000/svg';

  function buildChatIcon() {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('width', '26');
    svg.setAttribute('height', '26');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    var path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', 'M12 3C6.48 3 2 6.94 2 11.5c0 2.2 1.06 4.22 2.8 5.7L4 21l4.2-1.52c1.2.34 2.48.52 3.8.52 5.52 0 10-3.94 10-8.5S17.52 3 12 3z');
    path.setAttribute('fill', '#fff');
    svg.appendChild(path);
    return svg;
  }

  function buildCloseIcon() {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('width', '22');
    svg.setAttribute('height', '22');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    var path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', 'M6 6l12 12M18 6L6 18');
    path.setAttribute('stroke', '#fff');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('stroke-linecap', 'round');
    svg.appendChild(path);
    return svg;
  }

  function replaceIcon(parent, icon) {
    while (parent.firstChild) parent.removeChild(parent.firstChild);
    parent.appendChild(icon);
  }

  // --- DOM ------------------------------------------------------------------
  var button = document.createElement('button');
  button.className = 'pass24-chat-btn';
  button.style.zIndex = String(zIndex);
  button.setAttribute('aria-label', 'Открыть AI-помощник PASS24');
  button.title = 'AI-помощник PASS24';
  button.appendChild(buildChatIcon());

  var iframe = document.createElement('iframe');
  iframe.className = 'pass24-chat-frame';
  iframe.style.zIndex = String(zIndex - 1);
  iframe.setAttribute('title', 'AI-помощник PASS24');
  iframe.setAttribute('allow', 'clipboard-write');
  iframe.setAttribute('loading', 'lazy');
  iframe.src = widgetUrl;

  var isOpen = false;

  function open() {
    if (isOpen) return;
    isOpen = true;
    iframe.classList.add('is-open');
    replaceIcon(button, buildCloseIcon());
    button.setAttribute('aria-label', 'Закрыть AI-помощник PASS24');
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;
    iframe.classList.remove('is-open');
    replaceIcon(button, buildChatIcon());
    button.setAttribute('aria-label', 'Открыть AI-помощник PASS24');
  }

  function toggle() {
    if (isOpen) close(); else open();
  }

  button.addEventListener('click', toggle);

  // Свёртка по запросу из iframe (кнопка «—» внутри виджета)
  window.addEventListener('message', function (e) {
    // Принимаем только из iframe нашего origin
    if (!e.origin || e.origin !== host) return;
    if (e.data && e.data.type === 'pass24-chat:collapse') {
      close();
    }
  });

  // Esc закрывает открытый виджет
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) close();
  });

  function mount() {
    document.body.appendChild(iframe);
    document.body.appendChild(button);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
