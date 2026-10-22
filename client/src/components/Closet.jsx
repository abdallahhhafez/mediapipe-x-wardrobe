import React from 'react';
import { STRINGS, t } from '../i18n.js';

export default function Closet({ lang, items }) {
  return (
    <div>
      <div className="closet-head">
        <h2>{t(STRINGS.closet.title, lang)}</h2>
        <span className="closet-count">{t(STRINGS.closet.items, lang, items.length)}</span>
      </div>

      {items.length === 0 ? (
        <p className="empty">{t(STRINGS.closet.empty, lang)}</p>
      ) : (
        <div className="grid">
          {items.map(item => (
            <article key={item._id} className="item-card">
              <div className="img-wrap">
                {item.cutoutUrl && <img src={item.cutoutUrl} alt={item.name?.[lang] ?? ''} loading="lazy" />}
                {item.source === 'selfie' && (
                  <span className="selfie-badge">{t(STRINGS.closet.selfie, lang)}</span>
                )}
              </div>
              <div className="item-body">
                <div className="item-name">{item.name?.[lang] ?? item.name?.en}</div>
                <div className="item-meta">
                  <span className="swatch" style={{ background: item.color?.hex }} />
                  <span>{t(STRINGS.categories[item.category] ?? {}, lang)}</span>
                  <span className="wear-pill">{t(STRINGS.closet.worn, lang, item.wearCount)}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
