// Adapted from Aceternity UI "Aurora Background" (https://ui.aceternity.com), by Manu Arora.
// Changes: background layer only (no children wrapper), Nuqta colours, mask on the phone side, reduced motion,
// dark only, and no invert + difference-blend trick (it shifted our greens to pink/blue).
import type { CSSProperties } from 'react'

const STRIPES = (a: string, b: string, c: string, d: string, e: string) =>
  `repeating-linear-gradient(100deg,${a} 10%,${b} 15%,${c} 20%,${d} 25%,${e} 30%)`

const AURORA = STRIPES('#54a896', '#0b5d4f', '#a7d8cc', '#cf7f00', '#54a896')
const BLACK = 'repeating-linear-gradient(100deg,#000 0%,#000 7%,transparent 10%,transparent 12%,#000 16%)'

export function AuroraBackground({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
      style={{ '--aurora': AURORA, '--dark-gradient': BLACK } as CSSProperties}
    >
      <div
        className={`absolute -inset-[10px] opacity-40 blur-[10px] will-change-transform
        [background-image:var(--dark-gradient),var(--aurora)] [background-size:300%,200%] [background-position:50%_50%,50%_50%]
        after:absolute after:inset-0 after:content-[''] after:opacity-50 after:[background-attachment:fixed]
        after:[background-image:var(--dark-gradient),var(--aurora)] after:[background-size:200%,100%] after:animate-aurora
        motion-reduce:after:animate-none
        [mask-image:radial-gradient(ellipse_at_85%_15%,black_10%,transparent_65%)]
        rtl:[mask-image:radial-gradient(ellipse_at_15%_15%,black_10%,transparent_65%)]`}
      />
    </div>
  )
}
