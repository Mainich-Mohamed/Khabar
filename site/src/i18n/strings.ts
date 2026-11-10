export const strings = {
  en: {
    wordmark: 'Khabar',
    languageGroup: 'Language',
    home: 'Khabar, back to top',
    hero: {
      tagline: 'The news, read for you.',
      headline: 'Three short news emails a day. Every source linked.',
      subheadline:
        'Khabar reads 33 trusted outlets, merges the stories about the same event, and sends you a short brief. No app, no scrolling.',
    },
    outlets: { title: 'Khabar reads these outlets, and more' },
    form: {
      emailLabel: 'Your email',
      briefLangLabel: 'Brief language',
      soon: 'coming soon',
      submit: 'Send me the news',
      sending: 'Sending…',
      successTitle: 'Check your inbox',
      successBody: "We sent you a link. Tap it to start receiving Khabar. Can't find it? Look in your spam folder.",
      successArabic: "Arabic briefs are coming soon. We'll start sending them as soon as they're ready.",
      errors: {
        invalid: 'Enter a full email address, like name@example.com.',
        network: "We couldn't reach Khabar. Check your connection and try again.",
      },
    },
  },
  ar: {
    wordmark: 'خبر',
    languageGroup: 'اللغة',
    home: 'خبر، العودة إلى الأعلى',
    hero: {
      tagline: 'الأخبار، نقرأها نيابةً عنك.',
      headline: 'ثلاث رسائل إخبارية قصيرة كل يوم، وكل خبر بمصدره.',
      subheadline: 'يقرأ خبر 33 مصدرًا موثوقًا، ويجمع الأخبار عن الحدث نفسه، ويرسل لك ملخصًا قصيرًا. بلا تطبيق وبلا سكرول.',
    },
    outlets: { title: 'يقرأ خبر هذه المصادر وغيرها' },
    form: {
      emailLabel: 'بريدك الإلكتروني',
      briefLangLabel: 'لغة الملخص',
      soon: 'قريبًا',
      submit: 'أرسلوا لي الأخبار',
      sending: 'جارٍ الإرسال…',
      successTitle: 'تفقّد بريدك',
      successBody: 'أرسلنا لك رابطًا، اضغط عليه لتبدأ باستلام خبر. لا تجده؟ ابحث في مجلد الرسائل غير المرغوب فيها.',
      successArabic: 'الملخصات بالعربية قادمة قريبًا، وسنبدأ بإرسالها فور جاهزيتها.',
      errors: {
        invalid: 'أدخل بريدًا إلكترونيًا كاملًا، مثل \u2066name@example.com\u2069.',
        network: 'تعذّر الاتصال بخبر. تحقّق من اتصالك وحاول مرة أخرى.',
      },
    },
  },
} as const
