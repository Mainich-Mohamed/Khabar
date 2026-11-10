import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { Marquee } from './ui/marquee'

type Outlet = { file: string; name: string; ratio: number; invert?: boolean }

// Outlets Khabar reads (config/sources.yaml). Logos: Wikimedia Commons and the outlets' own sites.
// ratio: width ÷ height of the drawing, measured from each file.
// invert: the logo has black text, which disappears on our dark page. invert + hue-rotate turns
// black into white while keeping coloured parts close to their original hue.
const OUTLETS: Outlet[] = [
  { file: 'reuters.svg', name: 'Reuters', ratio: 3.65, invert: true },
  { file: 'ap.svg', name: 'Associated Press', ratio: 0.86 },
  { file: 'bbc.svg', name: 'BBC News', ratio: 3.32 },
  { file: 'aljazeera-mark.svg', name: 'Al Jazeera', ratio: 1 },
  { file: 'hespress.svg', name: 'Hespress', ratio: 3.91 },
  { file: 'dw.svg', name: 'DW', ratio: 1.75, invert: true },
  { file: 'ft-masthead.svg', name: 'Financial Times', ratio: 12.36, invert: true },
  { file: 'telquel.svg', name: 'TelQuel', ratio: 5.08 },
  { file: 'bloomberg.svg', name: 'Bloomberg', ratio: 5.43, invert: true },
  { file: 'medias24.svg', name: 'Médias24', ratio: 3.87, invert: true },
  { file: 'cnbc.svg', name: 'CNBC', ratio: 1.25, invert: true },
  { file: 'mee.svg', name: 'Middle East Eye', ratio: 1.79, invert: true },
  { file: 'foreignpolicy.svg', name: 'Foreign Policy', ratio: 1.58 },
  { file: 'techcrunch.svg', name: 'TechCrunch', ratio: 2 },
  { file: 'mittr.svg', name: 'MIT Technology Review', ratio: 2, invert: true },
  { file: 'nature.svg', name: 'Nature', ratio: 4.08, invert: true },
  { file: 'ieee.svg', name: 'IEEE Spectrum', ratio: 7.33, invert: true },
]

// Equal area, not equal height: at the same height a long wordmark covers several times the
// space of a square mark. Every logo gets about AREA px², with the height clamped so square
// marks don't grow huge and long wordmarks don't shrink to a hairline.
const AREA = 3400
const MIN_H = 16 // only the FT masthead (ratio 12) reaches this
const MAX_H = 44

function logoSize(ratio: number) {
  const height = Math.min(MAX_H, Math.max(MIN_H, Math.sqrt(AREA / ratio)))
  return { width: Math.round(height * ratio), height: Math.round(height) }
}

export function OutletStrip() {
  const { lang } = useLanguage()
  const t = strings[lang].outlets

  return (
    <section aria-labelledby="outlets-title" className="pt-8 pb-24">
      <h2 id="outlets-title" className="text-center text-sm font-medium text-muted rtl:text-base">{t.title}</h2>
      {/* dir="ltr": logos have no reading order, and the scroll maths assumes left-to-right layout */}
      <Marquee
        dir="ltr"
        pauseOnHover
        className="mt-6 [--duration:70s] [--gap:4rem] [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]"
      >
        {OUTLETS.map((o) => (
          <img
            key={o.file}
            src={`${import.meta.env.BASE_URL}logos/${o.file}`}
            alt={o.name}
            style={logoSize(o.ratio)}
            className={`shrink-0 self-center object-contain opacity-85 ${
              o.invert ? '[filter:invert(1)_hue-rotate(180deg)]' : ''}`}
          />
        ))}
      </Marquee>
    </section>
  )
}
