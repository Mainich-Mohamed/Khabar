import { MotionConfig } from 'motion/react'
import { Faq } from './components/Faq'
import { FinalSignup } from './components/FinalSignup'
import { Footer } from './components/Footer'
import { Hero } from './components/Hero'
import { WhatYouGet } from './components/WhatYouGet'
import { OutletStrip } from './components/OutletStrip'
import { TopBar } from './components/TopBar'
import { TrustSection } from './components/TrustSection'
import { LanguageProvider } from './i18n/LanguageProvider'

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <LanguageProvider>
        <TopBar />
        <main id="top">
          <Hero />
          <OutletStrip />
          <WhatYouGet />
          <TrustSection />
          <Faq />
          <FinalSignup />
        </main>
        <Footer />
      </LanguageProvider>
    </MotionConfig>
  )
}
