import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { BrainThin, GitMergeThin, LinkSimpleThin, NewspaperThin } from './ui/phosphor-icons'

// One icon per promise, in the same order as strings.trust.points
const ICONS = [GitMergeThin, NewspaperThin, LinkSimpleThin, BrainThin]

export function TrustSection() {
  const { lang } = useLanguage()
  const t = strings[lang].trust

  return (
    // Full-width tinted band: the one section that makes a claim, so it is set apart from the page colour
    <section aria-labelledby="trust-title" className="mb-32 border-y border-rule bg-aside">
     <div className="mx-auto grid max-w-6xl grid-cols-12 items-center gap-x-8 px-4 py-24">
      <div className="col-span-6">
        <h2 id="trust-title" className={`text-4xl font-semibold ${lang === 'ar' ? 'leading-snug' : 'tracking-tight'}`}>
          {t.title}
        </h2>
        <ul className="mt-12 space-y-8">
          {t.points.map((point, i) => {
            const PointIcon = ICONS[i]
            return (
              <li key={point.title} className="flex gap-5">
                <PointIcon className="mt-0.5 size-7 shrink-0 text-saffron" />
                <div>
                  {/* rtl: one size up, because Arabic glyphs look smaller than Latin ones at the same size */}
                  <h3 className="text-lg font-semibold rtl:text-xl">{point.title}</h3>
                  <p className="mt-1 max-w-[46ch] leading-relaxed text-muted rtl:text-lg">{point.body}</p>
                </div>
              </li>
            )
          })}
        </ul>
      </div>

      {/* The proof: two stories laid out like they are in the email (app/digest.py _story).
          Source names are plain text, not links, so nobody clicks into a made-up story.
          bg-paper: darker than the band, so the panel stands out of it instead of vanishing into it. */}
      <figure className="col-span-5 col-start-8 rounded-3xl border border-rule bg-paper p-8 shadow-2xl shadow-black/30">
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
     </div>
    </section>
  )
}
