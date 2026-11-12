import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { NuqtaMark } from './NuqtaMark'

const REPO_URL = 'https://github.com/Mainich-Mohamed/Khabar'

export function Footer() {
  const { lang } = useLanguage()
  const t = strings[lang]

  return (
    <footer className="border-t border-rule">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-8 px-4 py-10 text-sm text-muted">
        <div className="flex items-center gap-3">
          <NuqtaMark className="size-8" />
          <span className="text-base font-semibold text-ink">{t.wordmark}</span>
          <span>{t.hero.tagline}</span>
        </div>
        <div className="flex items-center gap-6">
          <a
            href={REPO_URL}
            className="rounded-sm underline-offset-4 hover:text-ink hover:underline focus-visible:outline-2
              focus-visible:outline-offset-4 focus-visible:outline-brand"
          >
            {t.footer.source}
          </a>
          <span dir="ltr">© {new Date().getFullYear()} Khabar</span>
        </div>
      </div>
    </footer>
  )
}
