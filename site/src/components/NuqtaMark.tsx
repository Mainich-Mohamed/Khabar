import { motion, useReducedMotion } from 'motion/react'

export const BOWL_PATH = 'M7 24 A53 33 0 0 0 113 24 L93 24 A33 17 0 0 1 27 24 Z'

type Props = {
  className?: string
  /** Drop the dot in on first render. Off for repeated uses (e.g. the footer). */
  animateDot?: boolean
}

export function NuqtaMark({ className, animateDot = false }: Props) {
  const reduceMotion = useReducedMotion()
  const drop = animateDot && !reduceMotion

  return (
    <svg viewBox="0 0 120 120" className={className} aria-hidden="true" focusable="false">
      <path className="fill-brand" d={BOWL_PATH} />
      <motion.circle
        className="fill-saffron"
        cx={60}
        cy={84}
        r={13}
        initial={drop ? { y: -60, opacity: 0 } : false}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 380, damping: 18, delay: 0.25 }}
      />
    </svg>
  )
}
