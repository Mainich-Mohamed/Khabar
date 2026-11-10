import { MotionConfig } from 'motion/react'
import { Hero } from './components/Hero'
import { OutletStrip } from './components/OutletStrip'
import { TopBar } from './components/TopBar'
import { LanguageProvider } from './i18n/LanguageProvider'

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <LanguageProvider>
        <TopBar />
        <main id="top" className="min-h-[200vh]">
          <Hero />
          <OutletStrip />
        </main>
      </LanguageProvider>
    </MotionConfig>
  )
}
