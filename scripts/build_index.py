#!/usr/bin/env python3
"""Turn the branded mockup into a production Telegram Mini App page."""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path("/workspace/course-miniapp/mockup/index.html")
DEST = Path("/workspace/tpes-import-toolkit/index.html")

LOADER = r'''
let TNVED = [];
let TNVED_META = null;
let tnvedLoading = null;

function ruDate(iso){
  if(!iso) return "";
  const m=String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : iso;
}

function updateSourceNote(){
  const el=$("#tnved-source");
  if(!el) return;
  const m=TNVED_META||{};
  const n=(m.codes!=null?m.codes:TNVED.length).toLocaleString("ru-RU");
  const notes=m.source_notes_date||"";
  const asof=m.as_of ? ruDate(m.as_of) : "";
  el.innerHTML = `Справочник — официальный ЕТТ ЕАЭС (файлы ЕЭК`+(notes?`, примечания на ${escapeHtml(notes)}`:"")+`). Состояние на ${escapeHtml(asof||"—")}. Кодов: ${n}. `+
    `Антидемпинговые и специальные пошлины, акциз и тарифные преференции справочником не определяются. Окончательные код и ставка подтверждает декларант.`+
    (m.source_url?` <a href="${escapeHtml(m.source_url)}" target="_blank" rel="noopener">Источник ЕЭК</a>.`:"");
}

function loadTnved(){
  if(TNVED.length) return Promise.resolve(TNVED);
  if(tnvedLoading) return tnvedLoading;
  const el=$("#tnved-source");
  if(el && !el.dataset.loaded) el.textContent="Загрузка полного справочника ТН ВЭД…";
  tnvedLoading=fetch("data/tnved.json")
    .then(r=>{ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
    .then(data=>{
      TNVED = data.codes || [];
      TNVED_META = data.meta || null;
      updateSourceNote();
      if(el) el.dataset.loaded="1";
      return TNVED;
    })
    .catch(err=>{
      tnvedLoading=null;
      if(el) el.textContent="Не удалось загрузить справочник ТН ВЭД. Проверьте сеть и обновите страницу.";
      console.error(err);
      throw err;
    });
  return tnvedLoading;
}

'''

def sub(t, old, new, label, count=1):
    n = t.count(old)
    if n != count:
        raise SystemExit(f"{label}: expected {count}, got {n}\n---\n{old[:200]}")
    return t.replace(old, new, count)

def main() -> None:
    t = SRC.read_text(encoding="utf-8")

    t = sub(t,
        '<html lang="ru" data-theme="light">',
        '<html lang="ru">',
        "html theme attr")

    t = sub(t,
        '<title>Тулкит «Импорт из Китая» — ТПЭС</title>\n<style>',
        '''<title>Тулкит «Импорт из Китая» — ТПЭС</title>
<meta name="description" content="Практический тулкит ТПЭС: калькулятор стоимости ввоза, документы, проверка поставщика и разбор ошибок при импорте из Китая.">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>''',
        "head script")

    # layout: full viewport, no fake phone chrome
    t = sub(t,
'''#stage, #app {
  width: 390px; height: 100%; max-height: 100vh; margin: 0 auto;
  background-color: var(--tg-theme-bg-color);''',
'''#stage, #app {
  width: 100%; height: 100%; max-height: 100%; margin: 0 auto;
  background-color: var(--tg-theme-bg-color);''',
        "full width")

    t = sub(t,
        "  --status-h: 44px;\n",
        "  --status-h: 0px;\n",
        "status-h", count=1)
    # only first :root has it? dark block might not have --status-h. good.

    # hide leftover status styles if any remain — we'll drop the HTML
    t = sub(
        t,
        ".status {\n",
        ".status { display: none !important;\n",
        "hide status css")

    # drop status bar HTML
    t = re.sub(
        r'  <div class="status">.*?</div>\n  <header class="topbar">',
        '  <header class="topbar">',
        t,
        count=1,
        flags=re.S,
    )
    if '<div class="status">' in t:
        raise SystemExit("status bar still present")
    print("ok removed status bar")

    # drop theme toggle
    t = re.sub(
        r'\n    <button class="icon-btn" type="button" id="btn-theme"[^>]*>.*?</button>\n',
        "\n",
        t,
        count=1,
        flags=re.S,
    )
    if 'id="btn-theme"' in t:
        raise SystemExit("theme button still present")
    print("ok removed theme toggle")

    # topbar: when Telegram BackButton is used, hide in-app back
    t = sub(t,
        "#app[data-view]:not([data-view=\"home\"]) .topbar .icon-btn.back { visibility: visible; }",
        '''#app[data-view]:not([data-view="home"]) .topbar .icon-btn.back { visibility: visible; }
#app.tg-native-back .icon-btn.back { display: none; }
#app {
  padding-top: env(safe-area-inset-top, 0px);
  padding-bottom: env(safe-area-inset-bottom, 0px);
}''',
        "safe area + hide in-app back")

    # source note under duty card
    t = sub(t,
        '''        <p class="muted">Антидемпинговые и специальные пошлины, акциз и тарифные преференции справочником не определяются. Окончательные код и ставка подтверждает декларант.</p>
      </div>''',
        '''        <p class="muted" id="tnved-source">Полный справочник ТН ВЭД ЕАЭС загружается при открытии калькулятора.</p>
      </div>''',
        "source note")

    # Replace inlined sample TNVED with lazy loader (slice, not re.sub — loader has regex escapes)
    m = re.search(r"const TNVED = \[.*?\];\nconst CONTENT", t, flags=re.S)
    if not m:
        raise SystemExit("TNVED array not found")
    t = t[:m.start()] + LOADER + "\nconst CONTENT" + t[m.end():]
    print("ok replaced TNVED array")

    # show(): load tnved on calc, sync back button
    t = sub(t,
'''function show(view){
  state.view=view;
  $("#app").dataset.view=view;
  $all(".view").forEach(v=>v.classList.toggle("on", v.id==="view-"+view));
  $all(".tab").forEach(t=>t.classList.toggle("on", t.dataset.view===view));
  $("#top-title").textContent=TITLES[view]||"Тулкит";
  $("#main").scrollTop=0;
  if(history.replaceState) history.replaceState(null,"","#"+ (view==="home"?"":view));
  else location.hash=view==="home"?"":view;
}''',
'''function syncTelegramBack(view){
  const tw=window.Telegram && window.Telegram.WebApp;
  if(!tw || !tw.BackButton) return;
  if(view==="home") tw.BackButton.hide();
  else tw.BackButton.show();
}

function show(view){
  state.view=view;
  $("#app").dataset.view=view;
  $all(".view").forEach(v=>v.classList.toggle("on", v.id==="view-"+view));
  $all(".tab").forEach(t=>t.classList.toggle("on", t.dataset.view===view));
  $("#top-title").textContent=TITLES[view]||"Тулкит";
  $("#main").scrollTop=0;
  if(history.replaceState) history.replaceState(null,"","#"+ (view==="home"?"":view));
  else location.hash=view==="home"?"":view;
  syncTelegramBack(view);
  if(view==="calc") loadTnved().catch(()=>{});
}''',
        "show()+back+lazy")

    # applyTariff: footnote until / RF
    t = sub(t,
'''  if(item.fn) html+=`<br>Применено примечание ${escapeHtml(item.fn)}С)${item.printed?" (в таблице ЕТТ: "+escapeHtml(item.printed)+")":""}. Источник — официальный ЕТТ ЕАЭС, файл на ${escapeHtml(item.src)}.`;
  else html+=`<br>Источник: официальный ЕТТ ЕАЭС, файл на ${escapeHtml(item.src)}.`;''',
'''  if(item.fn){
    const until=item.fnUntil?`, действует до ${ruDate(item.fnUntil)}`:"";
    const rf=item.fnRf?" для ввоза в РФ":"";
    const printed=item.printed?" (в таблице ЕТТ: "+escapeHtml(item.printed)+")":"";
    html+=`<br>Применено примечание ${escapeHtml(item.fn)}С)${rf}${until}${printed}. Источник — официальный ЕТТ ЕАЭС, файл на ${escapeHtml(item.src||"—")}.`;
  } else if(item.src){
    html+=`<br>Источник: официальный ЕТТ ЕАЭС, файл на ${escapeHtml(item.src)}.`;
  }''',
        "applyTariff footnotes")

    # not-found message: no longer a sample subset
    t = sub(t,
        '"В этом макете справочник содержит выборку кодов из официального ЕТТ. Этот код в выборку не входит — ставку можно ввести вручную в %."',
        '"Этого кода нет в официальном справочнике ЕТТ, загруженном в приложение. Проверьте цифры или введите ставку вручную в %."',
        "not-found copy")

    # boot: Telegram ready/expand, theme, BackButton, no toggle
    t = sub(t,
'''function boot(){
  const tp=window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.themeParams;
  if(tp){
    Object.entries(tp).forEach(([k,v])=>{ if(v) document.documentElement.style.setProperty("--tg-theme-"+k.replace(/_/g,"-"), v); });
    if(window.Telegram.WebApp.colorScheme==="dark") document.documentElement.setAttribute("data-theme","dark");
    const brand="#ff6232";
    ["--tg-theme-button-color","--tg-theme-link-color","--tg-theme-accent-text-color"].forEach(p=>document.documentElement.style.setProperty(p, brand));
    document.documentElement.style.setProperty("--tg-theme-button-text-color", "#ffffff");
  } else if(!document.documentElement.getAttribute("data-theme")) {
    document.documentElement.setAttribute("data-theme","light");
  }
  const tb=$("#tabbar");''',
'''function applyTheme(){
  const tw=window.Telegram && window.Telegram.WebApp;
  const brand="#ff6232";
  const lockBrand=()=>{
    ["--tg-theme-button-color","--tg-theme-link-color","--tg-theme-accent-text-color"].forEach(p=>document.documentElement.style.setProperty(p, brand));
    document.documentElement.style.setProperty("--tg-theme-button-text-color", "#ffffff");
  };
  if(tw && tw.themeParams){
    Object.entries(tw.themeParams).forEach(([k,v])=>{ if(v) document.documentElement.style.setProperty("--tg-theme-"+k.replace(/_/g,"-"), v); });
    const dark = tw.colorScheme==="dark";
    document.documentElement.setAttribute("data-theme", dark?"dark":"light");
    lockBrand();
  } else {
    const dark=window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", dark?"dark":"light");
  }
}

function boot(){
  const tw=window.Telegram && window.Telegram.WebApp;
  if(tw){
    try{ tw.ready(); }catch(e){}
    try{ tw.expand(); }catch(e){}
    if(tw.BackButton){
      tw.BackButton.onClick(()=>show("home"));
      if(tw.initDataUnsafe || tw.initData) $("#app").classList.add("tg-native-back");
      // Use Telegram BackButton whenever the API is present (Mini App or debug).
      $("#app").classList.add("tg-native-back");
    }
    if(tw.onEvent) tw.onEvent("themeChanged", applyTheme);
  }
  applyTheme();
  if(window.matchMedia){
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", ()=>{
      if(!(window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData)) applyTheme();
    });
  }
  const tb=$("#tabbar");''',
        "boot telegram")

    t = sub(t,
'''  $("#btn-back").onclick=()=>show("home");
  $("#btn-theme").onclick=()=>{
    const cur=document.documentElement.getAttribute("data-theme")==="dark"?"dark":"light";
    document.documentElement.setAttribute("data-theme", cur==="dark"?"light":"dark");
  };
  $all("[data-go]").forEach(b=>b.addEventListener("click",()=>show(b.dataset.go)));''',
'''  $("#btn-back").onclick=()=>show("home");
  $all("[data-go]").forEach(b=>b.addEventListener("click",()=>show(b.dataset.go)));''',
        "remove toggle js")

    # lazy-load when typing a code before dataset is ready
    t = sub(t,
'''  inp.addEventListener("input",()=>{
    const q=inp.value.trim();
    const digits=q.replace(/\\D/g,"");''',
'''  inp.addEventListener("input",()=>{
    const q=inp.value.trim();
    const digits=q.replace(/\\D/g,"");
    if(digits.length>=2 && !TNVED.length){
      loadTnved().then(()=>inp.dispatchEvent(new Event("input"))).catch(()=>{});
      return;
    }''',
        "input lazy load")

    # hash #calc should load (show already does this if TITLES[h])
    if 'id="btn-theme"' in t:
        raise SystemExit("theme remnants")
    if "const TNVED = [" in t:
        raise SystemExit("sample TNVED still inlined")
    if "telegram-web-app.js" not in t:
        raise SystemExit("telegram script missing")

    DEST.write_text(t, encoding="utf-8")
    print("WROTE", DEST, "bytes", DEST.stat().st_size)


if __name__ == "__main__":
    main()
