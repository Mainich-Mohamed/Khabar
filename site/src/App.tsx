import { MotionConfig } from 'motion/react'
import { TopBar } from './components/TopBar'
import { LanguageProvider } from './i18n/LanguageProvider'

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <LanguageProvider>
        <TopBar />
        <main id="top" className="mx-auto min-h-[200vh] max-w-6xl px-4 pt-28">
          <p className="text-muted">Page content will go here.</p>
        </main>
      </LanguageProvider>
    </MotionConfig>
  )
}
