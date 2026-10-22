import React, { useRef, useState } from 'react';
import { STRINGS, t } from '../i18n.js';
import { ingestPhoto } from '../api.js';

const STAGE_KEYS = ['finding', 'identifying', 'checking'];

export default function Upload({ lang, onResult }) {
  const [stage, setStage] = useState(-1);       // -1 idle, 0..2 running
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef();

  const run = async file => {
    if (!file) return;
    setError(null);
    setStage(0);
    // staged narration while the single pipeline call runs
    const t1 = setTimeout(() => setStage(1), 2500);
    const t2 = setTimeout(() => setStage(2), 6000);
    try {
      const result = await ingestPhoto(file);
      clearTimeout(t1); clearTimeout(t2);
      setStage(-1);
      if (result.rejectReason) {
        setError(result.rejectReason);
      } else if (!result.garments?.length) {
        setError('no_garments');
      } else {
        onResult(result);
      }
    } catch (e) {
      clearTimeout(t1); clearTimeout(t2);
      setStage(-1);
      setError(e.message);
    }
  };

  if (stage >= 0) {
    return (
      <div className="stages" aria-live="polite">
        {STAGE_KEYS.map((k, i) => (
          <div key={k} className={`stage ${i === stage ? 'active' : i < stage ? 'done' : ''}`}>
            <span className="spinner" aria-hidden="true" />
            {t(STRINGS.stages[k], lang)}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="upload-wrap">
      <h1 className="upload-title">{t(STRINGS.upload.title, lang)}</h1>
      <p className="upload-sub">{t(STRINGS.upload.sub, lang)}</p>

      <div
        className={`dropzone ${drag ? 'drag' : ''}`}
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); run(e.dataTransfer.files?.[0]); }}
      >
        <input ref={inputRef} type="file" accept="image/*"
          onChange={e => run(e.target.files?.[0])} />
        <button className="pick-btn" onClick={() => inputRef.current.click()}>
          {t(STRINGS.upload.pick, lang)}
        </button>
        <p style={{ color: 'var(--ink-2)', marginBottom: 0 }}>{t(STRINGS.upload.drop, lang)}</p>
      </div>

      <p className="privacy-note">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"
            stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        </svg>
        {t(STRINGS.upload.privacy, lang)}
      </p>

      {error && (
        <div className="error-box" role="alert">
          {t(STRINGS.errors[error] ?? STRINGS.errors.pipeline_failed, lang)}
        </div>
      )}
    </div>
  );
}
