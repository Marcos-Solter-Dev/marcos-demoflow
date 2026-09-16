from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import platform
import subprocess

from .chrome_tabs import ChromeTab


@dataclass(frozen=True)
class SiteElement:
    selector: str
    label: str
    kind: str
    doc_y: float
    score: float
    safe_click: bool = False
    href: str = ""


@dataclass(frozen=True)
class SiteAnalysis:
    title: str
    url: str
    doc_height: int
    viewport_height: int
    elements: list[SiteElement]


def _run_osascript(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )


def _execute_javascript(tab: ChromeTab, javascript: str) -> tuple[bool, str, str]:
    if platform.system() != "Darwin":
        return False, "", "A análise automática do DOM está disponível no macOS nesta versão."

    # Base64 evita problemas de aspas/quebras de linha ao transportar JS pelo AppleScript.
    payload = base64.b64encode(javascript.encode("utf-8")).decode("ascii")
    wrapped = f"eval(atob('{payload}'))"
    script = f'''
if application "Google Chrome" is not running then return "__DF_ERROR__:CHROME_NOT_RUNNING"
tell application "Google Chrome"
    if (count of windows) < {tab.window_index} then return "__DF_ERROR__:WINDOW_NOT_FOUND"
    if (count of tabs of window {tab.window_index}) < {tab.tab_index} then return "__DF_ERROR__:TAB_NOT_FOUND"
    try
        set resultText to execute tab {tab.tab_index} of window {tab.window_index} javascript "{wrapped}"
        return resultText
    on error errText number errNum
        return "__DF_ERROR__:" & (errNum as text) & ":" & errText
    end try
end tell
'''
    proc = _run_osascript(script)
    raw = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return False, "", stderr or raw or "Falha ao executar JavaScript no Chrome."
    if raw.startswith("__DF_ERROR__:"):
        detail = raw.split("__DF_ERROR__:", 1)[1]
        lower = detail.lower()
        if "javascript" in lower and ("apple" in lower or "event" in lower or "disabled" in lower or "turned off" in lower):
            return False, "", (
                "O Chrome bloqueou a análise automática. No Google Chrome, abra "
                "Visualizar → Desenvolvedor e habilite ‘Permitir JavaScript de eventos da Apple’ "
                "(o nome pode variar um pouco conforme o idioma), depois tente novamente."
            )
        return False, "", detail
    return True, raw, ""


def _analysis_javascript() -> str:
    # Mantido em ASCII para o transporte base64/atob ser previsível.
    return r'''(() => {
  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, 110);
  const esc = (s) => (window.CSS && CSS.escape) ? CSS.escape(String(s)) : String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  const unique = (s) => { try { return document.querySelectorAll(s).length === 1; } catch (_) { return false; } };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width >= 2 && r.height >= 2 && st.display !== 'none' && st.visibility !== 'hidden' && Number(st.opacity || 1) > 0.02;
  };
  const labelOf = (el) => clean(
    el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText ||
    el.getAttribute('placeholder') || el.getAttribute('value') || el.getAttribute('alt') || el.tagName
  );
  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) {
      const s = '#' + esc(el.id);
      if (unique(s)) return s;
    }
    const tag = el.tagName.toLowerCase();
    for (const attr of ['data-testid', 'data-test', 'name', 'aria-label']) {
      const val = el.getAttribute(attr);
      if (val && val.length < 100) {
        const q = tag + '[' + attr + '=' + JSON.stringify(val) + ']';
        if (unique(q)) return q;
      }
    }
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        parts.unshift('#' + esc(node.id));
        break;
      }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter(x => x.tagName === node.tagName);
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      const candidate = parts.join(' > ');
      if (unique(candidate)) return candidate;
      node = parent;
    }
    return parts.join(' > ');
  };
  const danger = (text) => /delete|remove|logout|log out|sign out|checkout|purchase|buy now|pay|subscribe|cancel subscription|excluir|remover|apagar|sair|comprar|pagar|assinar|finalizar compra/i.test(text);
  const rows = [];
  const add = (el, kind, baseScore) => {
    if (!visible(el)) return;
    const r = el.getBoundingClientRect();
    const selector = cssPath(el);
    if (!selector) return;
    const label = labelOf(el);
    if (!label && !['section','footer','main'].includes(kind)) return;
    const href = el.href || el.getAttribute('href') || '';
    const onclick = el.getAttribute('onclick') || '';
    const inForm = !!el.closest('form');
    const inAnchor = !!el.closest('a[href]') && el.tagName.toLowerCase() !== 'a';
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const samePage = tag === 'a' && (String(el.getAttribute('href') || '').startsWith('#') || String(el.getAttribute('href') || '') === '');
    const buttonSafe = (tag === 'button' || el.getAttribute('role') === 'button') && !inForm && !inAnchor && type !== 'submit' && !/location|window\.open|href/i.test(onclick);
    const safeClick = !danger(label) && (samePage || buttonSafe);
    const area = Math.min(25000, Math.max(0, r.width * r.height));
    rows.push({
      selector, label: label || kind, kind,
      doc_y: Math.max(0, r.top + window.scrollY),
      score: baseScore + Math.min(20, area / 1500),
      safe_click: !!safeClick,
      href: String(href || '').slice(0, 300)
    });
  };

  document.querySelectorAll('h1').forEach(el => add(el, 'heading', 115));
  document.querySelectorAll('h2').forEach(el => add(el, 'heading', 95));
  document.querySelectorAll('h3').forEach(el => add(el, 'heading', 78));
  document.querySelectorAll('main, main section, section[id], footer').forEach(el => add(el, el.tagName.toLowerCase(), 55));
  document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]').forEach(el => add(el, 'button', 92));
  document.querySelectorAll('a[href]').forEach(el => add(el, 'link', 67));

  const seen = new Set();
  const compact = rows
    .sort((a,b) => a.doc_y - b.doc_y || b.score - a.score)
    .filter(x => { const k = x.selector + '|' + x.kind; if (seen.has(k)) return false; seen.add(k); return true; })
    .slice(0, 180);

  return JSON.stringify({
    title: document.title || '',
    url: location.href,
    doc_height: Math.max(
        document.documentElement ? document.documentElement.scrollHeight : 0,
        document.documentElement ? document.documentElement.offsetHeight : 0,
        document.documentElement ? document.documentElement.clientHeight : 0,
        document.body ? document.body.scrollHeight : 0,
        document.body ? document.body.offsetHeight : 0,
        document.body ? document.body.clientHeight : 0
      ),
    viewport_height: window.innerHeight,
    elements: compact
  });
})()'''


def _parse_analysis_payload(raw: str) -> SiteAnalysis:
    data = json.loads(raw)
    elements: list[SiteElement] = []
    for item in data.get("elements", []):
        try:
            elements.append(SiteElement(
                selector=str(item.get("selector") or ""),
                label=str(item.get("label") or "").strip(),
                kind=str(item.get("kind") or "unknown"),
                doc_y=float(item.get("doc_y") or 0.0),
                score=float(item.get("score") or 0.0),
                safe_click=bool(item.get("safe_click", False)),
                href=str(item.get("href") or ""),
            ))
        except (TypeError, ValueError):
            continue
    return SiteAnalysis(
        title=str(data.get("title") or ""),
        url=str(data.get("url") or ""),
        doc_height=max(0, int(data.get("doc_height") or 0)),
        viewport_height=max(0, int(data.get("viewport_height") or 0)),
        elements=elements,
    )


def inspect_chrome_site(tab: ChromeTab) -> tuple[bool, SiteAnalysis | None, str]:
    ok, raw, error = _execute_javascript(tab, _analysis_javascript())
    if not ok:
        return False, None, error
    try:
        return True, _parse_analysis_payload(raw), ""
    except Exception as exc:
        return False, None, f"O Chrome respondeu, mas não consegui interpretar a análise do site: {exc}"


def scroll_element_into_view(tab: ChromeTab, selector: str) -> tuple[bool, str]:
    q = json.dumps(selector)
    js = f'''(() => {{
      const el = document.querySelector({q});
      if (!el) return "NOT_FOUND";
      el.scrollIntoView({{behavior:"smooth", block:"center", inline:"center"}});
      return "OK";
    }})()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, error
    return (raw.strip() == "OK"), ("" if raw.strip() == "OK" else raw.strip())


def get_element_screen_geometry(tab: ChromeTab, selector: str) -> tuple[bool, dict[str, float] | None, str]:
    q = json.dumps(selector)
    js = f'''(() => {{
      const el = document.querySelector({q});
      if (!el) return JSON.stringify({{found:false}});
      const r = el.getBoundingClientRect();
      const chromeX = Math.max(0, (window.outerWidth - window.innerWidth) / 2);
      const chromeY = Math.max(0, window.outerHeight - window.innerHeight);
      return JSON.stringify({{
        found:true,
        screen_x: window.screenX + chromeX + r.left + r.width / 2,
        screen_y: window.screenY + chromeY + r.top + r.height / 2,
        width:r.width, height:r.height,
        viewport_x:r.left + r.width / 2,
        viewport_y:r.top + r.height / 2,
        inner_width:window.innerWidth,
        inner_height:window.innerHeight
      }});
    }})()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, None, error
    try:
        data = json.loads(raw)
        if not data.get("found"):
            return False, None, "Elemento não encontrado após a rolagem."
        return True, {k: float(v) for k, v in data.items() if k != "found"}, ""
    except Exception as exc:
        return False, None, f"Geometria inválida retornada pelo Chrome: {exc}"


def capture_site_point(tab: ChromeTab, screen_x: float, screen_y: float) -> tuple[bool, dict[str, object] | None, str]:
    """Captura um ponto como coordenada do documento e, quando possível, ancora no elemento DOM.

    screen_x/screen_y usam o mesmo sistema de coordenadas empregado pelo PyAutoGUI/Quartz.
    O resultado guarda doc_x/doc_y, scroll atual, scroll ideal para centralizar o ponto e
    um seletor CSS + offset interno no elemento quando houver um elemento utilizável.
    """
    sx = float(screen_x)
    sy = float(screen_y)
    js = f'''(() => {{
      const clean = (s) => String(s || '').replace(/\\s+/g, ' ').trim().slice(0, 110);
      const esc = (s) => (window.CSS && CSS.escape) ? CSS.escape(String(s)) : String(s).replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');
      const unique = (s) => {{ try {{ return document.querySelectorAll(s).length === 1; }} catch (_) {{ return false; }} }};
      const cssPath = (el) => {{
        if (!el || el.nodeType !== 1) return '';
        if (el.id) {{ const s = '#' + esc(el.id); if (unique(s)) return s; }}
        const tag = el.tagName.toLowerCase();
        for (const attr of ['data-testid','data-test','name','aria-label']) {{
          const val = el.getAttribute(attr);
          if (val && val.length < 100) {{
            const q = tag + '[' + attr + '=' + JSON.stringify(val) + ']';
            if (unique(q)) return q;
          }}
        }}
        const parts = [];
        let node = el;
        while (node && node.nodeType === 1 && parts.length < 7) {{
          let part = node.tagName.toLowerCase();
          if (node.id) {{ parts.unshift('#' + esc(node.id)); break; }}
          const parent = node.parentElement;
          if (parent) {{
            const same = Array.from(parent.children).filter(x => x.tagName === node.tagName);
            if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
          }}
          parts.unshift(part);
          const candidate = parts.join(' > ');
          if (unique(candidate)) return candidate;
          node = parent;
        }}
        return parts.join(' > ');
      }};
      const labelOf = (el) => clean(
        el && (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText ||
        el.getAttribute('placeholder') || el.getAttribute('value') || el.getAttribute('alt') || el.tagName)
      );

      const chromeX = Math.max(0, (window.outerWidth - window.innerWidth) / 2);
      const chromeY = Math.max(0, window.outerHeight - window.innerHeight);
      const viewportX = {sx!r} - (window.screenX + chromeX);
      const viewportY = {sy!r} - (window.screenY + chromeY);
      if (viewportX < 0 || viewportY < 0 || viewportX > window.innerWidth || viewportY > window.innerHeight) {{
        return JSON.stringify({{found:false, reason:'OUTSIDE_VIEWPORT'}});
      }}

      const docHeight = Math.max(
        document.documentElement ? document.documentElement.scrollHeight : 0,
        document.documentElement ? document.documentElement.offsetHeight : 0,
        document.documentElement ? document.documentElement.clientHeight : 0,
        document.body ? document.body.scrollHeight : 0,
        document.body ? document.body.offsetHeight : 0,
        document.body ? document.body.clientHeight : 0
      );
      const maxScroll = Math.max(0, docHeight - window.innerHeight);
      const docX = window.scrollX + viewportX;
      const docY = window.scrollY + viewportY;
      const targetScrollY = Math.max(0, Math.min(maxScroll, docY - window.innerHeight * 0.48));
      let el = document.elementFromPoint(viewportX, viewportY);
      if (el && el.nodeType === 3) el = el.parentElement;
      const r = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
      const ox = r && r.width > 0 ? Math.max(0, Math.min(1, (viewportX - r.left) / r.width)) : 0.5;
      const oy = r && r.height > 0 ? Math.max(0, Math.min(1, (viewportY - r.top) / r.height)) : 0.5;
      const tag = el && el.tagName ? el.tagName.toLowerCase() : '';
      let kind = tag;
      if (el && (tag === 'button' || el.getAttribute('role') === 'button')) kind = 'button';
      else if (tag === 'a') kind = 'link';
      else if (/^h[1-6]$/.test(tag)) kind = 'heading';
      else if (tag === 'input' || tag === 'textarea' || tag === 'select') kind = 'field';

      return JSON.stringify({{
        found:true,
        selector: cssPath(el),
        label: labelOf(el),
        kind,
        doc_x: docX,
        doc_y: docY,
        capture_scroll_y: window.scrollY,
        target_scroll_y: targetScrollY,
        viewport_x: viewportX,
        viewport_y: viewportY,
        viewport_height: window.innerHeight,
        viewport_width: window.innerWidth,
        doc_height: docHeight,
        element_offset_x: ox,
        element_offset_y: oy,
        url: location.href
      }});
    }})()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, None, error
    try:
        data = json.loads(raw)
        if not data.get("found"):
            reason = data.get("reason") or "POINT_NOT_FOUND"
            return False, None, f"O ponto não ficou dentro da área da página ({reason})."
        return True, data, ""
    except Exception as exc:
        return False, None, f"Não consegui interpretar a posição do site: {exc}"


def get_page_scroll_state(tab: ChromeTab) -> tuple[bool, dict[str, float] | None, str]:
    js = '''(() => JSON.stringify({
      scroll_y: window.scrollY,
      scroll_x: window.scrollX,
      viewport_height: window.innerHeight,
      viewport_width: window.innerWidth,
      doc_height: Math.max(
        document.documentElement ? document.documentElement.scrollHeight : 0,
        document.documentElement ? document.documentElement.offsetHeight : 0,
        document.documentElement ? document.documentElement.clientHeight : 0,
        document.body ? document.body.scrollHeight : 0,
        document.body ? document.body.offsetHeight : 0,
        document.body ? document.body.clientHeight : 0
      )
    }))()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, None, error
    try:
        data = json.loads(raw)
        return True, {k: float(v) for k, v in data.items()}, ""
    except Exception as exc:
        return False, None, f"Estado de scroll inválido: {exc}"


def scroll_page_to(tab: ChromeTab, target_y: float, behavior: str = "smooth", duration: float | None = None) -> tuple[bool, str]:
    y = max(0.0, float(target_y))
    behavior = "auto" if behavior == "auto" else "smooth"
    duration_ms = 0 if duration is None else max(80, min(6000, int(float(duration) * 1000)))
    if duration_ms > 0:
        js = f'''(() => {{
          const docHeight = Math.max(
        document.documentElement ? document.documentElement.scrollHeight : 0,
        document.documentElement ? document.documentElement.offsetHeight : 0,
        document.documentElement ? document.documentElement.clientHeight : 0,
        document.body ? document.body.scrollHeight : 0,
        document.body ? document.body.offsetHeight : 0,
        document.body ? document.body.clientHeight : 0
      );
          const maxScroll = Math.max(0, docHeight - window.innerHeight);
          const target = Math.max(0, Math.min(maxScroll, {y!r}));
          const start = window.scrollY;
          const delta = target - start;
          const duration = {duration_ms};
          const ease = (t) => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
          const t0 = performance.now();
          const step = (now) => {{
            const p = Math.max(0, Math.min(1, (now - t0) / duration));
            window.scrollTo(window.scrollX, start + delta * ease(p));
            if (p < 1) requestAnimationFrame(step);
            else window.scrollTo(window.scrollX, target);
          }};
          requestAnimationFrame(step);
          return JSON.stringify({{ok:true, target, start, duration}});
        }})()'''
    else:
        js = f'''(() => {{
          const docHeight = Math.max(
        document.documentElement ? document.documentElement.scrollHeight : 0,
        document.documentElement ? document.documentElement.offsetHeight : 0,
        document.documentElement ? document.documentElement.clientHeight : 0,
        document.body ? document.body.scrollHeight : 0,
        document.body ? document.body.offsetHeight : 0,
        document.body ? document.body.clientHeight : 0
      );
          const maxScroll = Math.max(0, docHeight - window.innerHeight);
          const y = Math.max(0, Math.min(maxScroll, {y!r}));
          window.scrollTo({{top:y, left:window.scrollX, behavior:{json.dumps(behavior)}}});
          return JSON.stringify({{ok:true, target:y, current:window.scrollY, maxScroll}});
        }})()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, error
    return True, ""




def scroll_page_continuous(
    tab: ChromeTab,
    speed_px_s: float = 460.0,
) -> tuple[bool, dict[str, float] | None, str]:
    '''Inicia um scroll contínuo baseado em velocidade real e altura dinâmica.'''
    speed = max(120.0, min(1200.0, float(speed_px_s)))
    js = f'''(() => {{
      if (window.__demoFlowContinuousScroll && window.__demoFlowContinuousScroll.raf) {{
        cancelAnimationFrame(window.__demoFlowContinuousScroll.raf);
      }}

      const root = document.documentElement;
      const body = document.body;
      const previous = {{
        rootBehavior: root ? root.style.scrollBehavior : "",
        bodyBehavior: body ? body.style.scrollBehavior : "",
        rootSnap: root ? root.style.scrollSnapType : "",
        bodySnap: body ? body.style.scrollSnapType : ""
      }};

      if (root) {{
        root.style.scrollBehavior = "auto";
        root.style.scrollSnapType = "none";
      }}
      if (body) {{
        body.style.scrollBehavior = "auto";
        body.style.scrollSnapType = "none";
      }}

      const docHeight = () => Math.max(
        root ? root.scrollHeight : 0,
        root ? root.offsetHeight : 0,
        root ? root.clientHeight : 0,
        body ? body.scrollHeight : 0,
        body ? body.offsetHeight : 0,
        body ? body.clientHeight : 0
      );
      const maxScroll = () => Math.max(0, docHeight() - window.innerHeight);
      const restore = () => {{
        if (root) {{
          root.style.scrollBehavior = previous.rootBehavior;
          root.style.scrollSnapType = previous.rootSnap;
        }}
        if (body) {{
          body.style.scrollBehavior = previous.bodyBehavior;
          body.style.scrollSnapType = previous.bodySnap;
        }}
      }};

      const state = {{
        active: true,
        done: false,
        cancelled: false,
        startY: window.scrollY,
        currentY: window.scrollY,
        maxScroll: maxScroll(),
        docHeight: docHeight(),
        viewportHeight: window.innerHeight,
        speed: {speed!r},
        velocity: 0,
        startedAt: performance.now(),
        lastAt: performance.now(),
        lastHeightChangeAt: performance.now(),
        raf: 0,
        previousStyles: previous
      }};
      window.__demoFlowContinuousScroll = state;

      const accel = Math.max(220, state.speed / 0.72);
      const EPS = 0.75;
      const STABLE_BOTTOM_MS = 180;

      const finish = (cancelled = false) => {{
        state.active = false;
        state.done = !cancelled;
        state.cancelled = cancelled;
        state.currentY = window.scrollY;
        state.maxScroll = maxScroll();
        state.docHeight = docHeight();
        state.elapsedMs = performance.now() - state.startedAt;
        state.raf = 0;
        restore();
      }};
      state.finish = finish;

      const step = (now) => {{
        if (!state.active) return;

        const previousMax = state.maxScroll;
        const liveDocHeight = docHeight();
        const liveMax = Math.max(0, liveDocHeight - window.innerHeight);
        if (Math.abs(liveMax - previousMax) > 1) {{
          state.lastHeightChangeAt = now;
        }}
        state.maxScroll = liveMax;
        state.docHeight = liveDocHeight;
        state.viewportHeight = window.innerHeight;

        const rawDt = Math.max(0, (now - state.lastAt) / 1000);
        const dt = Math.min(0.050, rawDt || (1 / 60));
        state.lastAt = now;

        const current = window.scrollY;
        const remaining = Math.max(0, liveMax - current);

        if (remaining <= EPS) {{
          if ((now - state.lastHeightChangeAt) >= STABLE_BOTTOM_MS) {{
            if (remaining > 0.01) window.scrollTo(window.scrollX, liveMax);
            finish(false);
            return;
          }}
          state.velocity = Math.max(0, state.velocity - accel * dt);
          state.raf = requestAnimationFrame(step);
          return;
        }}

        const stopLimitedSpeed = Math.sqrt(Math.max(0, 2 * accel * remaining));
        const desired = Math.min(state.speed, stopLimitedSpeed);

        if (state.velocity < desired) {{
          state.velocity = Math.min(desired, state.velocity + accel * dt);
        }} else {{
          state.velocity = Math.max(desired, state.velocity - accel * dt);
        }}

        const advance = Math.min(remaining, Math.max(0.05, state.velocity * dt));
        const nextY = Math.min(liveMax, current + advance);
        window.scrollTo(window.scrollX, nextY);

        state.currentY = nextY;
        state.raf = requestAnimationFrame(step);
      }};

      state.raf = requestAnimationFrame(step);
      return JSON.stringify({{
        ok:true,
        start:state.startY,
        maxScroll:state.maxScroll,
        docHeight:state.docHeight,
        viewportHeight:state.viewportHeight,
        speed:state.speed
      }});
    }})()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, None, error
    try:
        return True, json.loads(raw), ""
    except Exception:
        return True, {"speed": speed}, ""


def get_continuous_scroll_status(
    tab: ChromeTab,
) -> tuple[bool, dict[str, float | bool] | None, str]:
    js = r'''(() => {
      const s = window.__demoFlowContinuousScroll;
      const root = document.documentElement;
      const body = document.body;
      const docHeight = Math.max(
        root ? root.scrollHeight : 0,
        root ? root.offsetHeight : 0,
        root ? root.clientHeight : 0,
        body ? body.scrollHeight : 0,
        body ? body.offsetHeight : 0,
        body ? body.clientHeight : 0
      );
      if (!s) return JSON.stringify({
        exists:false, active:false, done:false, cancelled:false,
        currentY:window.scrollY,
        maxScroll:Math.max(0, docHeight-window.innerHeight),
        docHeight,
        viewportHeight:window.innerHeight,
        elapsedMs:0,
        speed:0,
        velocity:0
      });
      return JSON.stringify({
        exists:true,
        active:!!s.active,
        done:!!s.done,
        cancelled:!!s.cancelled,
        currentY:window.scrollY,
        maxScroll:Math.max(0, docHeight-window.innerHeight),
        docHeight,
        viewportHeight:window.innerHeight,
        elapsedMs:performance.now()-s.startedAt,
        speed:Number(s.speed||0),
        velocity:Number(s.velocity||0)
      });
    })()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, None, error
    try:
        return True, json.loads(raw), ""
    except Exception as exc:
        return False, None, f"Status do scroll contínuo inválido: {exc}"


def cancel_continuous_scroll(tab: ChromeTab) -> tuple[bool, str]:
    js = r'''(() => {
      const s = window.__demoFlowContinuousScroll;
      if (!s) return "OK";
      if (s.raf) cancelAnimationFrame(s.raf);
      s.active = false;
      s.cancelled = true;
      if (typeof s.finish === "function") {
        s.finish(true);
      }
      return "OK";
    })()'''
    ok, raw, error = _execute_javascript(tab, js)
    return ok, ("" if ok else error)


def get_document_point_screen_geometry(
    tab: ChromeTab,
    doc_x: float,
    doc_y: float,
    selector: str | None = None,
    element_offset_x: float | None = None,
    element_offset_y: float | None = None,
) -> tuple[bool, dict[str, float] | None, str]:
    selector_json = json.dumps(selector or "")
    dx = float(doc_x)
    dy = float(doc_y)
    ox = 0.5 if element_offset_x is None else max(0.0, min(1.0, float(element_offset_x)))
    oy = 0.5 if element_offset_y is None else max(0.0, min(1.0, float(element_offset_y)))
    js = f'''(() => {{
      const selector = {selector_json};
      let docX = {dx!r};
      let docY = {dy!r};
      let viewportX = docX - window.scrollX;
      let viewportY = docY - window.scrollY;
      if (selector) {{
        try {{
          const el = document.querySelector(selector);
          if (el) {{
            const r = el.getBoundingClientRect();
            viewportX = r.left + r.width * {ox!r};
            viewportY = r.top + r.height * {oy!r};
            docX = window.scrollX + viewportX;
            docY = window.scrollY + viewportY;
          }}
        }} catch (_) {{}}
      }}
      const chromeX = Math.max(0, (window.outerWidth - window.innerWidth) / 2);
      const chromeY = Math.max(0, window.outerHeight - window.innerHeight);
      return JSON.stringify({{
        found:true,
        screen_x: window.screenX + chromeX + viewportX,
        screen_y: window.screenY + chromeY + viewportY,
        viewport_x: viewportX,
        viewport_y: viewportY,
        doc_x: docX,
        doc_y: docY,
        scroll_y: window.scrollY,
        inner_height: window.innerHeight,
        inner_width: window.innerWidth,
        visible: viewportX >= 0 && viewportX <= window.innerWidth && viewportY >= 0 && viewportY <= window.innerHeight
      }});
    }})()'''
    ok, raw, error = _execute_javascript(tab, js)
    if not ok:
        return False, None, error
    try:
        data = json.loads(raw)
        if not data.get("found"):
            return False, None, "Ponto do documento não encontrado."
        return True, {k: float(v) for k, v in data.items() if k not in {"found", "visible"}} | {"visible": bool(data.get("visible"))}, ""
    except Exception as exc:
        return False, None, f"Geometria do ponto inválida: {exc}"
