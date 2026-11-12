import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { NuqtaMark } from './NuqtaMark'
import { SignupForm } from './SignupForm'

// The closing band: brand green with soft, static tonal glows behind a frosted glass card that
// holds the form. The headline matches the hero's size, so the end of the page answers its start.
export function FinalSignup() {
  const { lang } = useLanguage()
  const t = strings[lang].final

  return (
    <section aria-labelledby="final-title" className="relative isolate overflow-hidden bg-band">
      {/* Glows: big blurred patches, no animation. The glass card needs colour behind it to blur.
          Tonal on purpose: only brand greens and the page's near-black. Saffron blurred into green turns
          olive, so saffron stays only on the logo dot. Start/end are logical, so the patches mirror in Arabic. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 blur-[60px]">
        <div className="absolute -start-[10%] -top-[25%] h-[80%] w-[50%] rounded-full bg-paper opacity-70" />
        <div className="absolute -top-[30%] end-[5%] h-[80%] w-[50%] rounded-full bg-brand opacity-35" />
        <div className="absolute -bottom-[45%] start-[25%] h-[80%] w-[55%] rounded-full bg-paper opacity-55" />
        <div className="absolute -bottom-[30%] -end-[10%] h-[70%] w-[40%] rounded-full bg-brand opacity-25" />
      </div>

      <div className="mx-auto grid max-w-6xl grid-cols-12 items-center gap-x-8 px-4 py-24">
        <div className="col-span-6">
          <NuqtaMark className="size-16" />
          <h2
            id="final-title"
            className={`mt-4 text-balance font-semibold ${
              lang === 'ar' ? 'text-5xl leading-[1.3]' : 'text-[3.25rem] leading-[1.08] tracking-tight'}`}
          >
            {t.title}
          </h2>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-ink/85 rtl:text-xl">{t.body}</p>
        </div>

        {/* Frosted glass card: see-through dark fill, backdrop blur, thin light border, faint top highlight */}
        <div
          className="col-span-6 col-start-7 rounded-3xl border border-ink/15 bg-paper/35 p-8 backdrop-blur-xl
            shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_20px_50px_rgb(0_0_0/0.25)]"
        >
          {/* tone="onBand": the button is light instead of green on green */}
          <SignupForm id="final" tone="onBand" />
        </div>
      </div>
    </section>
  )
}
