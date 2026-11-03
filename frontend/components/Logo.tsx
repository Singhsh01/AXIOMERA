export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#8B7CFF" /><stop offset="1" stopColor="#38E1F0" /></linearGradient></defs>
        <rect width="32" height="32" rx="8" fill="#131B33" stroke="rgba(139,148,255,.25)" />
        <path d="M8 22 L16 10 L24 22" fill="none" stroke="url(#lg)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="8" cy="22" r="2.6" fill="#8B7CFF" /><circle cx="16" cy="10" r="2.6" fill="#3D7BFF" /><circle cx="24" cy="22" r="2.6" fill="#38E1F0" />
      </svg>
      <span className="font-display text-[19px] font-semibold tracking-[-0.03em]">Orkestr</span>
    </span>
  );
}
