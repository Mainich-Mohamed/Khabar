import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'

export function WhatYouGet() {
  const { lang } = useLanguage()
  const t = strings[lang].what
  const last = t.stops.length - 1

  return (
    <section aria-labelledby="what-title" className="mx-auto max-w-6xl px-4 pb-32">
      <h2 id="what-title" className={`text-4xl font-semibold ${lang === 'ar' ? 'leading-snug' : 'tracking-tight'}`}>
        {t.title}
      </h2>

      <ol className="mt-12 grid grid-cols-4">
        {t.stops.map((stop, i) => (
          <li key={stop.name}>
            {/* The dot and the line to the next stop. Stops 1-3 are one day, so their line is solid;
                the line before Sunday is dotted, because Sunday is weekly. */}
            <div className="flex items-center" aria-hidden="true">
              <span className={`size-3 shrink-0 rounded-full ${i === last ? 'bg-saffron' : 'bg-brand'}`} />
              {i < last && (
                <span
                  className={`mx-4 flex-1 border-t ${
                    i === last - 1 ? 'border-t-2 border-dotted border-brand/70' : 'border-brand/40'}`}
                />
              )}
            </div>
            <p className="mt-6 text-3xl font-semibold">{stop.time}</p>
            <h3 className="mt-2 text-lg font-semibold text-brand rtl:text-xl">{stop.name}</h3>
            <p className="mt-2 max-w-[30ch] pe-8 leading-relaxed text-muted rtl:text-lg">{stop.body}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
