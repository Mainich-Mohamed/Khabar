import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'

export function HowItWorks() {
  const { lang } = useLanguage()
  const t = strings[lang].how

  return (
    <section aria-labelledby="how-title" className="mx-auto max-w-6xl px-4 pt-8 pb-32">
      <h2 id="how-title" className={`text-4xl font-semibold ${lang === 'ar' ? 'leading-snug' : 'tracking-tight'}`}>
        {t.title}
      </h2>

      {/* gap-x-0: the line in each step runs right up to the next number, so the three read as one sequence */}
      <ol className="mt-12 grid grid-cols-3">
        {t.steps.map((step, i) => (
          <li key={step.title}>
            <div className="flex items-center" aria-hidden="true">
              <span className="grid size-10 shrink-0 place-items-center rounded-full border border-brand text-base font-semibold text-brand">
                {i + 1}
              </span>
              {i < t.steps.length - 1 && <span className="mx-4 h-px flex-1 bg-brand/40" />}
            </div>
            {/* rtl: sizes one step up, because Arabic glyphs look smaller than Latin ones at the same size */}
            <h3 className="mt-6 text-2xl font-semibold rtl:text-3xl">{step.title}</h3>
            <p className="mt-2 max-w-[34ch] pe-8 leading-relaxed text-muted rtl:text-lg">{step.body}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
