import { motion } from 'motion/react'
import { useLanguage, type Lang } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'

const OPTIONS: { code: Lang; label: string }[] = [
  { code: 'ar', label: 'العربية' },
  { code: 'en', label: 'English' },
]

export function LanguageSwitch() {
  const { lang, setLang } = useLanguage()

  return (
    <div role="group" aria-label={strings[lang].languageGroup} className="flex rounded-full border border-rule p-1">
      {OPTIONS.map((option) => {
        const active = option.code === lang
        return (
          <button
            key={option.code}
            type="button"
            lang={option.code}
            aria-pressed={active}
            onClick={() => setLang(option.code)}
            className={`relative min-h-11 rounded-full px-4 text-sm font-medium transition-colors
              focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand
              ${active ? 'text-on-brand' : 'text-muted hover:text-ink'}`}
          >
            {active && (
              <motion.span
                layoutId="language-pill"
                className="absolute inset-0 rounded-full bg-brand"
                transition={{ type: 'spring', stiffness: 500, damping: 35 }}
              />
            )}
            <span className="relative">{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}
