import React from 'react';

type Props = {
  size?: number;
  state?: 'processing' | 'success' | 'failed' | 'idle';
  title?: string;
};

export default function SecurityProcessingAnimation({ size = 64, state = 'idle', title }: Props) {
  const cls = `security-animation ${state}`;
  const stroke = state === 'failed' ? '#ff6b7d' : state === 'success' ? '#2ecf9a' : '#7aa7ff';
  return (
    <div className={cls} aria-hidden={false} title={title}>
      <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="g1" x1="0" x2="1">
            <stop offset="0" stopColor="#7aa7ff" />
            <stop offset="1" stopColor="#2dd4bf" />
          </linearGradient>
        </defs>
        <g className="shield">
          <rect x="6" y="12" width="52" height="40" rx="8" fill="url(#g1)" opacity="0.06" />
          <path d="M32 6c6.627 0 12 4.03 12 9v11.5c0 6.627-5.373 12-12 12s-12-5.373-12-12V15c0-4.97 5.373-9 12-9z" fill={stroke} opacity="0.18" />
          <path d="M32 8c5.523 0 10 3.358 10 7.5V27c0 5.523-4.477 10-10 10s-10-4.477-10-10V15.5C22 11.358 26.477 8 32 8z" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        {state === 'processing' && (
          <g transform="translate(16,20)">
            <circle cx="16" cy="8" r="6" stroke="#7aa7ff" strokeWidth="2" strokeOpacity="0.14" fill="none" />
            <path d="M8 8c2 6 12 6 14 0" stroke="#7aa7ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
          </g>
        )}
        {state === 'success' && (
          <g transform="translate(8,8)">
            <path d="M18 28l6 6 12-14" stroke="#2ecf9a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </g>
        )}
        {state === 'failed' && (
          <g transform="translate(8,8)">
            <path d="M18 18l12 12M30 18L18 30" stroke="#ff6b7d" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        )}
      </svg>
    </div>
  );
}
