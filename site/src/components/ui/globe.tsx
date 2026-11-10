// Adapted from Magic UI "Globe" (https://magicui.design), MIT License, Copyright (c) Magic UI.
// Changes: Nuqta colours, no city markers, reduced motion, no cn().
import createGlobe, { type COBEOptions } from 'cobe'
import { useMotionValue, useReducedMotion, useSpring } from 'motion/react'
import { useEffect, useRef } from 'react'

const MOVEMENT_DAMPING = 1400

const CONFIG: COBEOptions = {
  width: 1400,
  height: 1200,
  onRender: () => {},
  devicePixelRatio: 2,
  phi: 5.2, // Atlantic centred: US cities, London, Bonn and Morocco visible together
  theta: 0.25,
  dark: 0.9,
  diffuse: 1.2,
  mapSamples: 16000,
  mapBrightness: 10,
  mapBaseBrightness: 0,
  baseColor: [0.04, 0.36, 0.31], // #0b5d4f brand green
  markerColor: [0.95, 0.6, 0.1], // saffron
  glowColor: [0.08, 0.22, 0.19], // faint green halo, not a white ring
  markers: [],
}

export function Globe({ className = '' }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const phiRef = useRef(CONFIG.phi)
  const widthRef = useRef(0)
  const pointerStart = useRef<number | null>(null)
  const reduceMotion = useReducedMotion()

  const r = useMotionValue(0)
  const rs = useSpring(r, { mass: 1, damping: 30, stiffness: 100 })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const onResize = () => { widthRef.current = canvas.offsetWidth }
    window.addEventListener('resize', onResize)
    onResize()

    const globe = createGlobe(canvas, {
      ...CONFIG,
      width: widthRef.current * 2,
      height: widthRef.current * 2,
      onRender: (state) => {
        if (pointerStart.current === null && !reduceMotion) phiRef.current += 0.003 // slow spin
        state.phi = phiRef.current + rs.get()
        state.width = widthRef.current * 2
        state.height = widthRef.current * 2
      },
    })
    canvas.style.opacity = '1'
    return () => {
      globe.destroy()
      window.removeEventListener('resize', onResize)
    }
  }, [rs, reduceMotion])

  return (
    <div className={`relative aspect-square w-full ${className}`}>
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="size-full cursor-grab opacity-0 transition-opacity duration-700 [contain:layout_paint_size]"
        onPointerDown={(e) => { pointerStart.current = e.clientX; e.currentTarget.style.cursor = 'grabbing' }}
        onPointerUp={(e) => { pointerStart.current = null; e.currentTarget.style.cursor = 'grab' }}
        onPointerOut={(e) => { pointerStart.current = null; e.currentTarget.style.cursor = 'grab' }}
        onPointerMove={(e) => {
          if (pointerStart.current === null) return
          r.set(r.get() + (e.clientX - pointerStart.current) / MOVEMENT_DAMPING)
          pointerStart.current = e.clientX
        }}
      />
    </div>
  )
}
