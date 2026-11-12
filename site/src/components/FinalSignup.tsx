import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { NuqtaMark } from './NuqtaMark'
import { SignupForm } from './SignupForm'

// The only tinted band on the page: it marks the end and repeats the one action
export function FinalSignup() {
  const { lang } = useLanguage()
  const t = strings[lang].final

  return (
    <section aria-labelledby="final-title" className="mx-auto max-w-6xl px-4 pb-24">
      {/* Brand green glows from the heading's corner and fades to the page colour behind the form,
          so the green button keeps its contrast. rtl: the glow follows the heading to the right. */}
      <div
        className="grid grid-cols-12 items-center gap-x-8 rounded-3xl border border-rule px-12 py-16
          bg-[radial-gradient(ellipse_at_top_left,var(--color-band),var(--color-paper)_70%)]
          rtl:bg-[radial-gradient(ellipse_at_top_right,var(--color-band),var(--color-paper)_70%)]"
      >
        <div className="col-span-6">
          <NuqtaMark className="size-12" />
          <h2 id="final-title" className={`mt-6 text-balance text-4xl font-semibold ${lang === 'ar' ? 'leading-snug' : 'tracking-tight'}`}>
            {t.title}
          </h2>
          <p className="mt-4 max-w-md text-lg leading-relaxed text-ink/80 rtl:text-xl">{t.body}</p>
        </div>
        <div className="col-span-5 col-start-8">
          <SignupForm id="final" />
        </div>
      </div>
    </section>
  )
}
