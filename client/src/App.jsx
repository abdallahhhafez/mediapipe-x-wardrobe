import React, { useEffect, useState } from 'react';
import { STRINGS, t } from './i18n.js';
import Upload from './components/Upload.jsx';
import ReviewSheet from './components/ReviewSheet.jsx';
import Closet from './components/Closet.jsx';
import { fetchItems } from './api.js';

export default function App() {
  const [lang, setLang] = useState(() => localStorage.getItem('lang') ?? 'en');
  const [tab, setTab] = useState('ingest');
  const [result, setResult] = useState(null);      // IngestResult under review
  const [items, setItems] = useState([]);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    localStorage.setItem('lang', lang);
  }, [lang]);

  const loadItems = () => fetchItems().then(setItems).catch(() => {});
  useEffect(() => { loadItems(); }, []);

  // dev hook: ?demo=<url of a saved IngestResult> opens the review sheet
  useEffect(() => {
    const demo = new URLSearchParams(location.search).get('demo');
    if (demo) fetch(demo).then(r => r.json()).then(setResult).catch(() => {});
  }, []);

  const showToast = msg => {
    setToast(msg);
    setTimeout(() => setToast(null), 2600);
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">{t(STRINGS.appName, lang)}<span className="dot">.</span></div>
        <nav role="tablist">
          <button role="tab" aria-selected={tab === 'ingest'} className="tab"
            onClick={() => setTab('ingest')}>{t(STRINGS.tabs.ingest, lang)}</button>
          <button role="tab" aria-selected={tab === 'closet'} className="tab"
            onClick={() => setTab('closet')}>{t(STRINGS.tabs.closet, lang)}</button>
        </nav>
        <button className="lang-switch" onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}>
          {lang === 'ar' ? 'English' : 'العربية'}
        </button>
      </header>

      {tab === 'ingest' && (
        <Upload lang={lang} onResult={setResult} />
      )}
      {tab === 'closet' && (
        <Closet lang={lang} items={items} />
      )}

      {result && (
        <ReviewSheet
          lang={lang}
          result={result}
          onClose={() => setResult(null)}
          onCommitted={({ createdItems, loggedWears }) => {
            setResult(null);
            loadItems();
            setTab('closet');
            showToast(t(STRINGS.review.committed, lang));
          }}
        />
      )}

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
