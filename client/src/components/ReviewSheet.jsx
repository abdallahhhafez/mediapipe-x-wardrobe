import React, { useMemo, useState } from 'react';
import { STRINGS, TYPES, t } from '../i18n.js';
import { commit } from '../api.js';

const CATEGORIES = ['top', 'bottom', 'outerwear', 'shoes', 'dress', 'accessory'];
const FORMALITIES = ['formal', 'smart_casual', 'casual', 'sport'];

function initCard(g, lang) {
  const conf = g.attributes?.type?.confidence ?? 0;
  const typeVal = g.attributes?.type?.value;
  return {
    tempId: g.tempId,
    category: g.category,
    // accessories default to unselected (spec S7)
    included: g.category !== 'accessory',
    // matched items default to logging a wear
    action: g.match ? 'log_wear' : 'create',
    match: g.match,
    cutoutUrl: g.cutoutUrl,
    embedding: g.embedding,
    name: { ...g.generated?.name },
    description: { ...g.generated?.description },
    type: typeVal && typeVal !== 'unknown' ? typeVal : '',
    typeUnknown: !typeVal || typeVal === 'unknown',
    typePredicted: typeVal ?? 'unknown',
    typeConfidence: conf,
    color: g.attributes?.color,
    formality: g.attributes?.formality?.value ?? 'casual',
    attributes: g.attributes,
    quality: g.quality,
  };
}

export default function ReviewSheet({ lang, result, onClose, onCommitted }) {
  const [cards, setCards] = useState(() => result.garments.map(g => initCard(g, lang)));
  const [busy, setBusy] = useState(false);

  const update = (i, patch) =>
    setCards(cs => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const included = cards.filter(c => c.included);
  const nCreate = included.filter(c => c.action === 'create').length;
  const nWear = included.filter(c => c.action === 'log_wear').length;

  const doCommit = async () => {
    setBusy(true);
    try {
      const payload = included.map(c => ({
        action: c.action,
        existingItemId: c.match?.existingItemId,
        category: c.category,
        name: c.name, description: c.description,
        type: c.type || undefined,
        color: c.color ? {
          key: c.color.name?.key, en: c.color.name?.en, ar: c.color.name?.ar,
          hex: c.color.hex, lab: c.color.lab,
        } : undefined,
        formality: c.formality,
        attributes: {
          sleeve: c.attributes?.sleeve,
          length: c.attributes?.length,
          // what the parser saw (pants vs skirt) — keeps a later relabel
          // from turning trousers into a skirt off a cropped cutout
          bottomKind: c.attributes?.bottomKind,
          pattern: c.attributes?.pattern?.value,
          neckline: c.attributes?.neckline?.value,
        },
        cutoutUrl: c.cutoutUrl,
        sourceImageUrl: result.sourceImageUrl,
        embedding: c.embedding ?? undefined,
        corrections: c.typeUnknown && c.type ? [{
          field: 'type', predicted: c.typePredicted, corrected: c.type,
          confidence: c.typeConfidence, category: c.category,
        }] : [],
      }));
      const res = await commit(payload);
      onCommitted(res);
    } catch {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <section className="sheet" role="dialog" aria-modal="true"
        aria-label={t(STRINGS.review.title, lang)}>
        <div className="sheet-head">
          <h2 className="sheet-title">{t(STRINGS.review.title, lang)}</h2>
          <button className="sheet-close" onClick={onClose} aria-label="close">✕</button>
        </div>

        <div className="source-strip">
          {result.overlayUrl && <img src={result.overlayUrl} alt="" />}
          <div style={{ display: 'grid', gap: 8 }}>
            {result.personCount > 1 && (
              <div className="multi-note">{t(STRINGS.review.multiPerson, lang)}</div>
            )}
            {result.warnings?.includes('not_full_body') && (
              <div className="multi-note">{t(STRINGS.review.notFullBody, lang)}</div>
            )}
          </div>
        </div>

        {cards.map((c, i) => (
          <article key={c.tempId} className={`gcard ${c.included ? '' : 'deselected'}`}>
            <img className="cut" src={c.cutoutUrl} alt={c.name?.[lang] ?? ''} />
            <div>
              <div className="gcard-head">
                <span className="chip cat">
                  <select
                    value={c.category}
                    onChange={e => update(i, { category: e.target.value, type: '' })}
                    aria-label={t(STRINGS.review.type, lang)}>
                    {CATEGORIES.map(cat => (
                      <option key={cat} value={cat}>{t(STRINGS.categories[cat], lang)}</option>
                    ))}
                  </select>
                </span>
                {c.quality?.occluded && <span className="chip">{t(STRINGS.review.hidden, lang)}</span>}
                {c.quality?.warnings?.includes('unreliable_mask') && (
                  <span className="chip warn">{t(STRINGS.review.unreliable, lang)}</span>
                )}
                <label className="chip g-toggle">
                  <input type="checkbox" checked={c.included}
                    onChange={e => update(i, { included: e.target.checked })} />
                  {' '}{t(STRINGS.review.include, lang)}
                </label>
              </div>

              {c.match && c.action === 'log_wear' ? (
                <div className="match-box">
                  <span>{t(STRINGS.review.matched, lang)}</span>
                  <span style={{ color: 'var(--ink-2)', fontSize: 12 }}>
                    {(c.match.similarity * 100).toFixed(0)}%
                  </span>
                  <span className="match-actions">
                    <button className="btn-sm primary">{t(STRINGS.review.logWear, lang)}</button>
                    <button className="btn-sm"
                      onClick={() => update(i, { action: 'create' })}>
                      {t(STRINGS.review.differentItem, lang)}
                    </button>
                  </span>
                </div>
              ) : (
                <div className="fields">
                  <div className="field">
                    <label>{t(STRINGS.review.name, lang)}</label>
                    <input value={c.name?.[lang] ?? ''}
                      onChange={e => update(i, { name: { ...c.name, [lang]: e.target.value } })} />
                  </div>
                  <div className={`field ${c.typeUnknown && !c.type ? 'unknown' : ''}`}>
                    <label>{t(STRINGS.review.type, lang)}</label>
                    <select value={c.type}
                      onChange={e => update(i, { type: e.target.value })}>
                      <option value="">—</option>
                      {(TYPES[c.category] ?? []).map(tp => (
                        <option key={tp} value={tp}>{tp.replace(/_/g, ' ')}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>{t(STRINGS.review.color, lang)}</label>
                    <div className="color-row">
                      <span className="swatch" style={{ background: c.color?.hex }} />
                      <input value={c.color?.name?.[lang] ?? ''} readOnly />
                    </div>
                  </div>
                  <div className="field">
                    <label>{t(STRINGS.review.formality, lang)}</label>
                    <select value={c.formality}
                      onChange={e => update(i, { formality: e.target.value })}>
                      {FORMALITIES.map(f => (
                        <option key={f} value={f}>{t(STRINGS.formality[f], lang)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}
            </div>
          </article>
        ))}

        <footer className="sheet-footer">
          <button className="cta" disabled={busy || included.length === 0} onClick={doCommit}>
            {included.length === 0
              ? t(STRINGS.review.nothing, lang)
              : t(STRINGS.review.cta, lang, nCreate, nWear)}
          </button>
        </footer>
      </section>
    </>
  );
}
