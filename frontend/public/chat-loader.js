/**
 * PASS24 AI-chat widget loader.
 *
 * Встраиваемый скрипт для сторонних сайтов PASS24. Добавляет плавающую
 * кнопку AI-помощника, открывает чат в iframe с
 * https://support.pass24pro.ru/chat-widget.
 *
 * Использование на сайте клиента — одна строка перед </body>:
 *   <script src="https://support.pass24pro.ru/chat-loader.js" async></script>
 *
 * Никаких изменений бэкенда / CORS не требуется: все запросы AI и
 * создания заявок идут из iframe в домен support.pass24pro.ru (same-origin).
 *
 * Передача host-домена клиента: loader подмешивает `?host=<hostname>` в
 * URL iframe. Это позволяет backend в POST /tickets/guest найти Customer
 * по поддомену (bristol.pass24online.ru → "bristol") и автоматически
 * заполнить ticket.customer_id / company / object_name.
 *
 * Перетаскивание (только desktop). Конечный посетитель сайта может drag'ом
 * перенести кнопку в любой из 4 углов экрана — на pointerup кнопка прилипает
 * к ближайшему углу, окно чата перепривязывается к нему же (если кнопка
 * вверху — окно открывается под кнопкой). Выбор сохраняется в localStorage
 * текущего домена под ключом `pass24-chat-corner` и переживает перезагрузку.
 *
 * Опциональные data-атрибуты на теге <script>:
 *   data-host       — переопределить хост виджета (default: origin у script.src)
 *   data-z-index    — z-index кнопки и iframe (default: 2147483000)
 *   data-position   — НАЧАЛЬНЫЙ угол, если посетитель ещё не перетаскивал:
 *                     bottom-right (default) | bottom-left | top-right | top-left.
 *                     localStorage перебивает это значение.
 *   data-offset-x   — отступ по горизонтали от края, px (default: 24)
 *   data-offset-y   — отступ по вертикали от края, px (default: 24)
 *   data-frame-gap  — зазор между кнопкой и окном iframe по вертикали, px (default: 76)
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

  var ds = (currentScript && currentScript.dataset) || {};

  var scriptSrc = (currentScript && currentScript.src) || '';
  var defaultHost = scriptSrc ? new URL(scriptSrc).origin : 'https://support.pass24pro.ru';
  var host = ds.host || defaultHost;
  var zIndex = parseInt(ds.zIndex || '2147483000', 10);
  // window.location.hostname host-страницы (bristol.pass24online.ru). Backend
  // в POST /tickets/guest пытается матчнуть Customer по поддомену и заполнить
  // ticket.customer_id / company / object_name. Для не-pass24online.ru доменов
  // backend поле проигнорирует — видим только в логах.
  var embedHost = (window.location && window.location.hostname) || '';
  var widgetUrl = host.replace(/\/$/, '') + '/chat-widget';
  if (embedHost) {
    widgetUrl += '?host=' + encodeURIComponent(embedHost);
  }

  var POSITIONS = {
    'bottom-right': { h: 'right', v: 'bottom' },
    'bottom-left':  { h: 'left',  v: 'bottom' },
    'top-right':    { h: 'right', v: 'top' },
    'top-left':     { h: 'left',  v: 'top' }
  };
  var STORAGE_KEY = 'pass24-chat-corner';
  var initialPosition = POSITIONS[ds.position] ? ds.position : 'bottom-right';
  // localStorage перебивает data-position: посетитель один раз перетянул — и виджет
  // запоминает выбор для этого домена.
  try {
    var savedCorner = window.localStorage && window.localStorage.getItem(STORAGE_KEY);
    if (savedCorner && POSITIONS[savedCorner]) initialPosition = savedCorner;
  } catch (_e) { /* localStorage может быть отключён в Safari Private — fallback на data-position */ }

  function toInt(value, fallback) {
    var parsed = parseInt(value, 10);
    return (isFinite(parsed) && parsed >= 0) ? parsed : fallback;
  }
  var offsetX = toInt(ds.offsetX, 24);
  var offsetY = toInt(ds.offsetY, 24);
  var frameGap = toInt(ds.frameGap, 76);

  // iframe смещён на 8px внутрь по горизонтали (визуальный зазор, как в исходной раскладке)
  // и на offsetY + frameGap по вертикали — кнопка остаётся видна рядом с окном.
  var frameOffsetX = Math.max(0, offsetX - 8);
  var frameOffsetY = offsetY + frameGap;

  // --- Стили (инжектируются один раз) ---------------------------------------
  var styleId = 'pass24-chat-loader-style';
  if (!document.getElementById(styleId)) {
    var style = document.createElement('style');
    style.id = styleId;
    // textContent на элементе <style> — безопасно, это не парсится как HTML.

    // Базовая раскладка без привязки к углу — конкретные edges навешиваем
    // через corner-классы, чтобы можно было переключать позицию в рантайме.
    var css = [
      '.pass24-chat-btn{position:fixed;width:60px;height:60px;border-radius:50%;',
      'background:#0f172a;color:#fff;border:0;cursor:grab;box-shadow:0 10px 30px -6px rgba(15,23,42,0.4);',
      'display:flex;align-items:center;justify-content:center;transition:transform 0.15s,background 0.15s;',
      'font-family:-apple-system,BlinkMacSystemFont,sans-serif;touch-action:none;}',
      '.pass24-chat-btn:hover{transform:scale(1.05);background:#1e293b;}',
      '.pass24-chat-btn:focus{outline:2px solid #6366f1;outline-offset:3px;}',
      '.pass24-chat-btn.is-dragging{cursor:grabbing;transition:none;}',
      '.pass24-chat-btn.is-dragging:hover{transform:none;background:#0f172a;}',
      '.pass24-chat-frame{position:fixed;width:400px;max-width:calc(100vw - 32px);',
      'height:620px;border:0;border-radius:20px;background:transparent;',
      'box-shadow:0 24px 48px -12px rgba(15,23,42,0.25);display:none;color-scheme:light;}',
      '.pass24-chat-frame.is-open{display:block;}'
    ].join('');

    // Угловые классы — генерируются для всех 4 углов, чтобы переключать
    // позицию через classList.toggle без перерасчёта inline-стилей.
    Object.keys(POSITIONS).forEach(function (corner) {
      var e = POSITIONS[corner];
      css += '.pass24-chat-btn.corner-' + corner + '{'
          + e.h + ':' + offsetX + 'px;' + e.v + ':' + offsetY + 'px;}';
      css += '.pass24-chat-frame.corner-' + corner + '{'
          + e.h + ':' + frameOffsetX + 'px;' + e.v + ':' + frameOffsetY + 'px;'
          + 'max-height:calc(100vh - ' + (frameOffsetY + 20) + 'px);}';
    });

    // Bottom-sheet на мобильных — для обоих bottom-* углов. На top-* углах
    // кнопка может быть наверху, но окно всё равно растягиваем как bottom-sheet —
    // на маленьком экране это удобнее свободно-плавающего окна.
    css += '@media (max-width:480px){'
        + '.pass24-chat-frame.corner-bottom-right,'
        + '.pass24-chat-frame.corner-bottom-left{'
        + 'right:0;left:0;bottom:0;width:100%;max-width:100%;'
        + 'height:85vh;max-height:85vh;border-radius:20px 20px 0 0;}'
        + '.pass24-chat-btn{cursor:pointer;}'   // touch-устройства: drag отключён, обычный pointer
        + '}';
    style.textContent = css;
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
  button.className = 'pass24-chat-btn corner-' + initialPosition;
  button.style.zIndex = String(zIndex);
  button.setAttribute('aria-label', 'Открыть AI-помощник PASS24');
  button.title = 'AI-помощник PASS24';
  button.appendChild(buildChatIcon());

  var iframe = document.createElement('iframe');
  iframe.className = 'pass24-chat-frame corner-' + initialPosition;
  iframe.style.zIndex = String(zIndex - 1);
  iframe.setAttribute('title', 'AI-помощник PASS24');
  iframe.setAttribute('allow', 'clipboard-write');
  iframe.setAttribute('loading', 'lazy');
  iframe.src = widgetUrl;

  var isOpen = false;
  var currentCorner = initialPosition;

  // Переключение угла: меняем corner-классы на кнопке и iframe, сохраняем выбор.
  function applyCorner(corner) {
    if (!POSITIONS[corner]) return;
    Object.keys(POSITIONS).forEach(function (key) {
      button.classList.toggle('corner-' + key, key === corner);
      iframe.classList.toggle('corner-' + key, key === corner);
    });
    currentCorner = corner;
    try {
      if (window.localStorage) window.localStorage.setItem(STORAGE_KEY, corner);
    } catch (_e) { /* приватный режим — окей, на следующем визите вернётся к initial */ }
  }

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

  // --- Drag (только desktop) -----------------------------------------------
  // Тащим кнопку в любой из 4 углов; iframe двигается синхронно, чтобы
  // развёрнутый чат не «отрывался» от кнопки. На pointerup защёлкиваем
  // ближайший угол по фактическому центру кнопки и сохраняем в localStorage.
  var DRAG_THRESHOLD = 5; // px — меньше этого считается кликом, не drag
  var dragState = null;

  function isMobileViewport() {
    return !!(window.matchMedia && window.matchMedia('(max-width:480px)').matches);
  }

  function nearestCorner(rect) {
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var h = cx < window.innerWidth / 2 ? 'left' : 'right';
    var v = cy < window.innerHeight / 2 ? 'top' : 'bottom';
    return v + '-' + h;
  }

  function onPointerDown(e) {
    if (e.button !== 0 && e.pointerType === 'mouse') return; // только ЛКМ для мыши
    if (isMobileViewport()) return;                          // на мобильных drag не нужен
    dragState = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      moved: false
    };
    try { button.setPointerCapture(e.pointerId); } catch (_e) { /* старые браузеры */ }
  }

  function onPointerMove(e) {
    if (!dragState || e.pointerId !== dragState.pointerId) return;
    var dx = e.clientX - dragState.startX;
    var dy = e.clientY - dragState.startY;
    if (!dragState.moved && (dx * dx + dy * dy) < DRAG_THRESHOLD * DRAG_THRESHOLD) return;
    if (!dragState.moved) {
      dragState.moved = true;
      button.classList.add('is-dragging');
      // На время drag блокируем pointer-events внутри iframe — иначе курсор
      // может «провалиться» в iframe, и pointermove перестанут долетать до кнопки.
      iframe.style.pointerEvents = 'none';
    }
    // translate и кнопке, и iframe — оба следуют за курсором как одно целое.
    button.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
    if (isOpen) iframe.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
  }

  function onPointerUp(e) {
    if (!dragState || e.pointerId !== dragState.pointerId) return;
    var moved = dragState.moved;
    dragState = null;
    button.classList.remove('is-dragging');
    iframe.style.pointerEvents = '';
    if (moved) {
      // getBoundingClientRect учитывает transform — даёт реальное положение после drag.
      var rect = button.getBoundingClientRect();
      var newCorner = nearestCorner(rect);
      // Сначала снимаем transform (иначе corner-класс плюс transform = двойной сдвиг
      // при следующем кадре), затем применяем новый corner-класс.
      button.style.transform = '';
      iframe.style.transform = '';
      applyCorner(newCorner);
      // Браузер всё равно сгенерирует click после pointerup — гасим именно
      // следующий, чтобы перетаскивание не открывало/закрывало чат.
      button.addEventListener('click', swallowClickOnce, { capture: true, once: true });
    } else {
      button.style.transform = '';
      iframe.style.transform = '';
    }
  }

  function swallowClickOnce(e) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }

  button.addEventListener('pointerdown', onPointerDown);
  button.addEventListener('pointermove', onPointerMove);
  button.addEventListener('pointerup', onPointerUp);
  button.addEventListener('pointercancel', onPointerUp);

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
