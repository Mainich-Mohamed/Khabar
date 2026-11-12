import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'

export function TrustSection() {
  const { lang } = useLanguage()
  const t = strings[lang].trust

  return (
    <section aria-labelledby="trust-title" className="mx-auto grid max-w-6xl grid-cols-12 items-center gap-x-8 px-4 pb-32">
      <div className="col-span-6">
        <h2 id="trust-title" className={`text-4xl font-semibold ${lang === 'ar' ? 'leading-snug' : 'tracking-tight'}`}>
          {t.title}
        </h2>
        <ul className="mt-12 space-y-8">
          {t.points.map((point) => (
            <li key={point.title}>
              {/* rtl: one size up, because Arabic glyphs look smaller than Latin ones at the same size */}
              <h3 className="text-lg font-semibold rtl:text-xl">{point.title}</h3>
              <p className="mt-1 max-w-[46ch] leading-relaxed text-muted rtl:text-lg">{point.body}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* The proof: two stories laid out like they are in the email (app/digest.py _story).
          Source names are plain text, not links, so nobody clicks into a made-up story. */}
      <figure className="col-span-5 col-start-8 rounded-3xl border border-rule bg-aside p-8 shadow-2xl shadow-black/30">
        <figcaption className="text-sm text-muted">{t.example.label}</figcaption>
        {t.example.items.map((item, i) => (
          <article key={item.title} className={i === 0 ? 'mt-6' : 'mt-6 border-t border-rule pt-6'}>
            <p className="text-lg font-bold leading-snug rtl:text-xl">{item.title}</p>
            <p className="mt-1.5 leading-normal text-ink/85 rtl:text-lg">{item.summary}</p>
            <p className="mt-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px] rtl:text-sm">
              {item.sources.map((source) => (
                <span key={source} className="text-brand underline decoration-brand/40 underline-offset-2">{source}</span>
              ))}
              {item.single && <span className="text-xs text-muted rtl:text-[13px]">{t.example.singleSource}</span>}
            </p>
          </article>
        ))}
      </figure>
    </section>
  )
}
