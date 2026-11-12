import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'

// Native <details>: keyboard, screen readers and right-to-left work without any script
export function Faq() {
  const { lang } = useLanguage()
  const t = strings[lang].faq

  return (
    <section aria-labelledby="faq-title" className="mx-auto max-w-6xl px-4 pb-32">
      <h2 id="faq-title" className={`text-4xl font-semibold ${lang === 'ar' ? 'leading-snug' : 'tracking-tight'}`}>
        {t.title}
      </h2>

      <div className="mt-12 max-w-3xl border-b border-rule">
        {t.items.map((item) => (
          <details key={item.q} className="group border-t border-rule">
            <summary
              className="flex cursor-pointer list-none items-center justify-between gap-6 rounded-sm py-6 text-lg font-semibold
                rtl:text-xl hover:text-brand focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand
                [&::-webkit-details-marker]:hidden"
            >
              {item.q}
              {/* Plus that becomes a minus: the vertical bar turns flat when the answer opens */}
              <span aria-hidden="true" className="relative size-4 shrink-0 text-brand">
                <span className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-current" />
                <span
                  className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 rounded-full bg-current
                    transition-transform duration-200 group-open:rotate-90 motion-reduce:transition-none"
                />
              </span>
            </summary>
            <p className="max-w-[60ch] pb-6 leading-relaxed text-muted rtl:text-lg">{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  )
}
