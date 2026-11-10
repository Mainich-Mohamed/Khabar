// Adapted from Magic UI "Marquee" (https://magicui.design), MIT License, Copyright (c) Magic UI.
// Changes: no cn(), horizontal only, reverses in RTL, stops under reduced motion.
import type { ComponentPropsWithoutRef, ReactNode } from 'react'

interface MarqueeProps extends ComponentPropsWithoutRef<'div'> {
  pauseOnHover?: boolean
  repeat?: number
  children: ReactNode
}

export function Marquee({ className = '', pauseOnHover = false, repeat = 4, children, ...props }: MarqueeProps) {
  return (
    <div {...props} className={`group flex gap-(--gap) overflow-hidden [--duration:40s] [--gap:1rem] ${className}`}>
      {Array.from({ length: repeat }, (_, i) => (
        <div
          key={i}
          aria-hidden={i > 0 || undefined}
          className={`flex shrink-0 justify-around gap-(--gap) animate-marquee rtl:[animation-direction:reverse]
            motion-reduce:animate-none ${pauseOnHover ? 'group-hover:[animation-play-state:paused]' : ''}`}
        >
          {children}
        </div>
      ))}
    </div>
  )
}
