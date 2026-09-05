import React, { useState } from 'react';

const DigestItem = ({ item }) => {
  const [showDetails, setShowDetails] = useState(false);

  const tierBar = {
    'High attention': 'border-l-[3px] border-l-accent',
    'Worth knowing': 'border-l-[3px] border-l-warning',
    'Normal': 'border-l-[3px] border-l-line',
  };

  const tierBadges = {
    'High attention': 'High attention',
    'Worth knowing': 'Worth knowing',
    'Normal': 'Normal',
  };

  const isQuiet = item.tier === 'Normal';

  return (
    <div className={`${tierBar[item.tier] || 'border-l-[3px] border-l-line'} bg-card rounded-md p-4 mb-3 border border-line shadow-card card-hover`}>
      <div className="flex justify-between items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center flex-wrap gap-2 mb-1">
            <span className={`font-semibold ${isQuiet ? 'text-muted' : 'text-ink'}`}>{item.symbol}</span>
            <span className="text-[11px] text-muted bg-[var(--card-muted)] px-2 py-0.5 rounded">
              {item.event_type}
            </span>
          </div>
          <p className={`text-[13px] leading-relaxed mb-2 ${isQuiet ? 'text-muted' : 'text-ink'}`}>{item.description}</p>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="text-muted tabular">
              {new Date(item.timestamp).toLocaleString()}
            </span>
            <span className="text-muted">
              {tierBadges[item.tier]}
            </span>
            <span className="text-muted tabular">
              Score: {item.significance_score}
            </span>
          </div>
        </div>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-muted hover:text-accent text-[12px] font-medium ml-2 flex-shrink-0"
        >
          {showDetails ? 'Less' : 'Why?'}
        </button>
      </div>

      {showDetails && item.context?.reasons && (
        <div className="mt-3 p-3 bg-[var(--card-muted)] rounded-md border border-line animate-fade-in">
          <p className="text-[11px] font-medium text-muted mb-2">Why we're showing this</p>
          <ul className="space-y-1">
            {item.context.reasons.map((reason, idx) => (
              <li key={idx} className="text-[13px] text-ink flex items-start gap-2">
                <span className="text-accent mt-1.5 w-1 h-1 rounded-full bg-accent flex-shrink-0"></span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
          {item.context.price && (
            <p className="text-[11px] text-muted mt-2 pt-2 border-t border-line tabular">
              Current price: ₹{item.context.price.toFixed(2)}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default DigestItem;
