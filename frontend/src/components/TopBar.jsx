import React from 'react';
import { Cpu, Layers, LogOut, User } from 'lucide-react';

export default function TopBar({ sessionInfo, onSwitchAccount, onSwitchFactory }) {
  return (
    <header className="relative h-14 shrink-0 flex items-center justify-between px-5 bg-white/85 backdrop-blur-xl border-b border-slate-200/80 shadow-xs z-10">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-accent-primary to-accent-secondary flex items-center justify-center font-bold text-white text-base shadow-sm">
          P
        </div>
        <div className="leading-tight">
          <h1 className="font-extrabold text-sm text-slate-900 tracking-tight">Ad-PIE</h1>
          <p className="text-[11px] text-slate-700 font-semibold tracking-wide uppercase">
            Azure Data — Platform Intelligence Engine
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-semibold">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Engine Online</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-700 font-semibold pl-3 border-l border-border-color">
          <Cpu size={14} className="text-accent-primary" />
          <span>v3.0.0</span>
        </div>

        {/* Quick Switch Factory Action */}
        {onSwitchFactory && (
          <button
            onClick={onSwitchFactory}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-xs font-bold text-slate-700 hover:text-slate-900 transition-colors shadow-xs cursor-pointer ml-1"
            title="Switch Azure Data Factory or Subscription"
          >
            <Layers size={13} className="text-accent-primary" />
            <span>Switch Factory</span>
          </button>
        )}

        {/* User Account Info */}
        {sessionInfo && (
          <div className="flex items-center gap-2 pl-3 border-l border-slate-200">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-accent-primary to-accent-secondary text-white font-bold text-xs flex items-center justify-center shadow-xs">
              {sessionInfo?.claims?.display_name?.charAt(0) || sessionInfo?.user_id?.charAt(0) || <User size={13} />}
            </div>
            <div className="hidden lg:flex flex-col text-left max-w-[140px]">
              <span className="text-xs font-bold text-slate-900 leading-tight truncate">
                {sessionInfo?.claims?.display_name || 'Active Account'}
              </span>
              <span className="text-[10px] text-slate-500 font-medium leading-tight truncate">
                {sessionInfo?.user_id}
              </span>
            </div>
          </div>
        )}

        {/* Quick Switch Account Action */}
        {onSwitchAccount && (
          <button
            onClick={onSwitchAccount}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-xs font-bold text-slate-700 transition-colors shadow-xs cursor-pointer"
            title="Sign out and log into another Microsoft account"
          >
            <LogOut size={13} />
            <span>Switch Account</span>
          </button>
        )}
      </div>
    </header>
  );
}
