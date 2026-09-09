import React, { useState } from 'react';

export default function ActionMenu({ items }: { items: { id: string; label: string; onClick: () => void; visible?: boolean }[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button className="secondary" onClick={() => setOpen((s) => !s)}>•••</button>
      {open && (
        <div style={{ position: 'absolute', right: 0, top: 'calc(100% + 8px)', background: '#fff', color: '#111', borderRadius: 8, boxShadow: '0 8px 24px rgba(2,6,23,0.2)', minWidth: 220, zIndex: 1000 }}>
          {items.filter(i => i.visible !== false).map((item) => (
            <button key={item.id} onClick={() => { item.onClick(); setOpen(false); }} style={{ display: 'block', width: '100%', padding: '10px 12px', textAlign: 'left', border: 'none', background: 'transparent' }}>{item.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
