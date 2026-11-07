import { AnimatePresence, motion, useMotionValueEvent, useScroll } from 'motion/react'
import { useState } from 'react'
import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { LanguageSwitch } from './LanguageSwitch'
import { NuqtaMark } from './NuqtaMark'

const SCROLL_THRESHOLD = 24 // px scrolled before the bar becomes a floating pill

export function TopBar() {
  const { lang } = useLanguage()
  const { scrollY } = useScroll()
  const [scrolled, setScrolled] = useState(false)

  useMotionValueEvent(scrollY, 'change', (y) => setScrolled(y > SCROLL_THRESHOLD))

  return (
    <header className="fixed inset-x-0 top-5 z-50 px-4 pt-[env(safe-area-inset-top)]">
      <motion.div
        initial={false}
        animate={{
          maxWidth: scrolled ? 768 : 1152,
          y: scrolled ? 12 : 0,
          borderRadius: scrolled ? 9999 : 0,
        }}
        transition={{ type: 'spring', stiffness: 260, damping: 30 }}
        className={`mx-auto flex h-16 items-center justify-between gap-4 border pe-2 ps-4
          transition-[background-color,border-color,box-shadow] duration-300
          ${scrolled ? 'border-rule bg-paper/80 shadow-sm backdrop-blur-md' : 'border-transparent bg-transparent'}`}
      >
        <a
          href="#top"
          aria-label={strings[lang].home}
          className="flex items-center gap-2 rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
        >
          <NuqtaMark animateDot className="size-10" />
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={lang}
              lang={lang}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className={lang === 'ar' ? 'text-[1.7rem] font-semibold leading-none -translate-y-1' : 'text-2xl font-semibold tracking-tight leading-none -translate-y-1'}
            >
              {strings[lang].wordmark}
            </motion.span>
          </AnimatePresence>
        </a>
        <LanguageSwitch />
      </motion.div>
    </header>
  )
}
