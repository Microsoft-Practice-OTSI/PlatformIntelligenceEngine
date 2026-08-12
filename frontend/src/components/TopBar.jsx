import React from 'react';
import { Cpu } from 'lucide-react';

export default function TopBar() {
  return (
    <header className="relative h-14 shrink-0 flex items-center justify-between px-4 bg-bg-surface border-b border-border-color">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent-primary flex items-center justify-center font-bold text-white text-base shadow-lg shadow-accent-primary/20">
          P
        </div>
        <div className="leading-tight">
          <h1 className="font-bold text-base text-text-primary tracking-tight">Ad-PIE</h1>
          <p className="text-[10px] text-text-secondary uppercase tracking-wider font-semibold">
            Azure Data — Platform Intelligence Engine
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-text-secondary">
        <Cpu size={14} className="text-accent-secondary" />
        <span>Platform Intelligence Engine</span>
      </div>
    </header>
  );
}
