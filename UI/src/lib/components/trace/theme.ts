// src/lib/components/trace/theme.ts
//
// Design tokens cho trace module. Tập trung tại 1 chỗ để đảm bảo contrast
// nhất quán giữa các card.
//
// Palette đã tune cho nền tối #0a0a0c:
//   - Card nền #18181b (3 bậc sáng hơn nền app)
//   - Header card #232326 (4 bậc)
//   - Border #52525b (visible rõ với nền)
//   - Text primary #fafafa (trắng ngà — không chói)

export const T = {
  // Backgrounds
  bgCard: 'bg-[#18181b]',
  bgCardHeader: 'bg-[#232326]',
  bgInner: 'bg-[#0f0f11]',
  bgTerminal: 'bg-[#0a0a0c]',

  // Borders
  border: 'border-[#52525b]',
  borderSubtle: 'border-[#3f3f46]',

  // Text colors
  textPrimary: 'text-zinc-50',
  textSecondary: 'text-zinc-200',
  textLabel: 'text-zinc-400',
  textMuted: 'text-zinc-500',

  // Common combos
  card: 'rounded-lg border border-[#52525b] bg-[#18181b]',
  cardHeader: 'bg-[#232326] border-b border-[#52525b]',
  headerLabel: 'text-[10px] font-mono uppercase tracking-wider text-zinc-300',
  contentText: 'text-[12.5px] text-zinc-50 whitespace-pre-wrap break-words leading-relaxed',
  monoText: 'font-mono text-[11.5px] text-zinc-100',
} as const;