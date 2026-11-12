import { useState, type FormEvent } from 'react'
import { useLanguage } from '../i18n/LanguageProvider'
import { strings } from '../i18n/strings'
import { signup, type BriefLang } from '../lib/signup'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** `id` keeps label/field ids unique: the form appears twice on the page (hero and final section).
 *  `tone="onBand"`: the form sits on the solid brand-green panel, where brand-coloured parts would vanish */
export function SignupForm({ id, tone = 'default' }: { id: string; tone?: 'default' | 'onBand' }) {
  const onBand = tone === 'onBand'
  const { lang } = useLanguage()
  const t = strings[lang].form
  const [email, setEmail] = useState('')
  const [briefLang, setBriefLang] = useState<BriefLang>('en')
  const [status, setStatus] = useState<'idle' | 'sending' | 'done'>('idle')
  const [error, setError] = useState<'invalid' | 'network' | null>(null)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (new FormData(event.currentTarget).get('website')) return setStatus('done') // honeypot: a bot filled it
    if (!EMAIL_RE.test(email.trim())) return setError('invalid')
    setError(null)
    setStatus('sending')
    const result = await signup(email.trim(), briefLang)
    if (result.ok) {
      setStatus('done')
    } else {
      setError(result.reason)
      setStatus('idle')
    }
  }

  if (status === 'done') {
    return (
      <div role="status" className="max-w-md rounded-2xl border border-rule bg-paper p-5">
        <p className="text-lg font-semibold">{t.successTitle}</p>
        <p className="mt-1 text-muted">{t.successBody}</p>
        {briefLang === 'ar' && <p className="mt-2 text-muted">{t.successArabic}</p>}
      </div>
    )
  }

  return (
    <form noValidate onSubmit={onSubmit} className="max-w-md space-y-4">
      <div>
        <label htmlFor={`${id}-email`} className="text-sm font-medium">{t.emailLabel}</label>
        <input
          id={`${id}-email`} name="email" type="email" inputMode="email" autoComplete="email" dir="ltr"
          placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)}
          aria-invalid={error === 'invalid'} aria-describedby={error ? `${id}-error` : undefined}
          className="mt-1.5 block h-12 w-full rounded-xl border border-rule bg-paper px-4 text-base
            placeholder:text-muted/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30
            aria-[invalid=true]:border-danger"
        />
        {error && <p id={`${id}-error`} role="alert" className={`mt-1.5 text-sm ${onBand ? 'font-medium text-ink' : 'text-danger'}`}>{t.errors[error]}</p>}
      </div>

      <fieldset>
        <legend className="text-sm font-medium">{t.briefLangLabel}</legend>
        <div className="mt-1.5 flex gap-2">
          {(['en', 'ar'] as const).map((code) => (
            <label key={code} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border px-4 ${onBand
              ? 'border-ink/30 has-[:checked]:border-ink has-[:checked]:bg-ink/10'
              : 'border-rule has-[:checked]:border-brand has-[:checked]:bg-brand/5'}`}>
              <input type="radio" name="briefLang" value={code} checked={briefLang === code}
                onChange={() => setBriefLang(code)} className="accent-brand" />
              <span lang={code}>{code === 'en' ? 'English' : 'العربية'}</span>
              {code === 'ar' && <span className="whitespace-nowrap rounded-full bg-saffron/15 px-2 py-0.5 text-xs">{t.soon}</span>}
            </label>
          ))}
        </div>
      </fieldset>

      {/* Honeypot: invisible to people, bots tend to fill every field */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" className="absolute -start-[9999px]" />

      <button type="submit" disabled={status === 'sending'}
        className={`inline-flex h-12 items-center justify-center gap-2 rounded-xl px-6 font-medium
          transition hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-70 ${onBand
            ? 'bg-ink text-paper focus-visible:outline-ink'
            : 'bg-brand text-on-brand focus-visible:outline-brand'}`}>
        {status === 'sending' && <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
        {status === 'sending' ? t.sending : t.submit}
      </button>
    </form>
  )
}
