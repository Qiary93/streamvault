import React from 'react';
import { SealCheck } from '@phosphor-icons/react';

const colors = {
  Beginner: '#10B981',
  Intermediate: '#3B82F6',
  Advanced: '#A855F7',
  Expert: '#F59E0B',
};

export default function VerifiedBadge({ grade, size = 'sm' }) {
  if (!grade) return null;
  const color = colors[grade] || '#00E5FF';
  const iconSize = size === 'lg' ? 22 : size === 'md' ? 18 : 14;
  return (
    <span
      title={`Verified · ${grade}`}
      className="inline-flex items-center gap-1 align-middle"
      data-testid="verified-badge"
    >
      <SealCheck weight="fill" style={{ color }} width={iconSize} height={iconSize} />
    </span>
  );
}
