import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { Globe } from './ui/globe'
import { SignupForm } from './SignupForm'
import { AuroraBackground } from './ui/aurora-background'

export function Hero() {
  const { lang } = useLanguage()
  const t = strings[lang].hero

  return (
    <section className="relative isolate overflow-hidden">
      <AuroraBackground className="-z-10" />
      <div className="mx-auto grid min-h-svh max-w-6xl grid-cols-12 items-center gap-x-8 px-4 pb-24 pt-36">
      <div className="col-span-6">
        <p className="text-lg font-medium text-brand">{t.tagline}</p>
        <h1 className={`mt-4 text-balance font-semibold ${
          lang === 'ar' ? 'text-5xl leading-[1.3]' : 'text-[3.25rem] leading-[1.08] tracking-tight'}`}>
          {t.headline}
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">{t.subheadline}</p>
        <div className="mt-10">
          <SignupForm id="hero" />
        </div>
      </div>

      <div className="relative col-span-5 col-start-8 flex flex-col items-center">
        <Globe className="w-[520px] max-w-none shrink-0" />
      </div>
      </div>
    </section>
  )
}
