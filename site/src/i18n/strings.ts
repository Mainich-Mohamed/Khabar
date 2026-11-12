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
    what: {
      title: 'What you get',
      stops: [
        { time: '07:00', name: 'Morning brief', body: 'The top story first, then every topic in a few lines, with sources.' },
        { time: '16:00', name: 'Afternoon update', body: "Only what's new since the morning." },
        { time: '20:00', name: 'Evening brief', body: "The day in full, without repeating this morning's stories." },
        { time: 'Sunday 20:30', name: 'Khabar Artificial Expert', body: 'It rereads everything Khabar sent you that week, and explains what it means.' },
      ],
    },
    trust: {
      title: 'Why you can trust it',
      points: [
        { title: 'One event, one story.', body: 'When five outlets cover the same event, you read it once, with all five links.' },
        { title: 'Facts only from the articles.', body: 'An AI writes each summary from the articles themselves. A story only one outlet reports is marked single source.' },
        { title: "Links that can't be made up.", body: 'The AI never writes links. Khabar attaches the real article links itself.' },
        { title: "An expert that can't invent events.", body: 'On Sunday, the Khabar Artificial Expert works only from stories Khabar already sent you.' },
      ],
      example: {
        label: 'Example of two stories in a brief',
        singleSource: 'single source',
        items: [
          {
            title: 'Rabat opens its new tram line',
            summary: "Two new lines connect the city's outer districts to the centre, local authorities say.",
            sources: ['Hespress', 'Médias24', 'TelQuel'],
            single: false,
          },
          {
            title: 'Agadir port plans a larger fishing terminal',
            summary: 'The port authority says work could start next year.',
            sources: ['Médias24'],
            single: true,
          },
        ],
      },
    },
    faq: {
      title: 'Questions',
      items: [
        { q: 'Is Khabar free?', a: 'Yes. Khabar is free.' },
        { q: 'Which topics does it cover?', a: 'Six: geopolitics, Morocco, economy, tech and AI, software engineering, and science and engineering.' },
        { q: 'Which language are the briefs in?', a: 'English for now. Arabic briefs are coming soon. Khabar reads outlets in English, French and Arabic.' },
        { q: 'Who writes the briefs?', a: 'An AI model writes each summary from the articles Khabar reads. It never writes the links: Khabar attaches the real article links itself.' },
        { q: 'Why do I need to confirm my email?', a: 'So no one can sign you up without asking you. Tap the link we send you and the briefs start.' },
        { q: 'How do I unsubscribe?', a: 'Every email has an unsubscribe link at the bottom. One tap and the emails stop.' },
        { q: 'What do you do with my email?', a: 'We use it only to send you the briefs. We never sell or share it.' },
      ],
    },
    final: {
      title: 'Get the next brief in your inbox',
      body: 'Three short emails a day, and one analysis on Sunday. Free.',
    },
    footer: {
      source: 'Source code on GitHub',
    },
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
    what: {
      title: 'ماذا يصلك',
      stops: [
        { time: '07:00', name: 'ملخص الصباح', body: 'أهم خبر أولًا، ثم كل موضوع في أسطر قليلة، مع المصادر.' },
        { time: '16:00', name: 'تحديث بعد الظهر', body: 'ما استجدّ فقط منذ الصباح.' },
        { time: '20:00', name: 'ملخص المساء', body: 'اليوم كاملًا، دون تكرار أخبار الصباح.' },
        { time: 'الأحد 20:30', name: 'خبير خبر الاصطناعي', body: 'يعيد قراءة كل ما أرسله خبر إليك خلال الأسبوع، ويشرح ما يعنيه.' },
      ],
    },
    trust: {
      title: 'لماذا تثق بخبر',
      points: [
        { title: 'خبر واحد لكل حدث.', body: 'حين تغطي خمسة مصادر الحدث نفسه، تقرأه مرة واحدة، مع روابطها الخمسة.' },
        { title: 'وقائع من المقالات فقط.', body: 'يكتب ذكاء اصطناعي كل ملخص من المقالات نفسها، والخبر الذي ينفرد به مصدر واحد يُوسم «مصدر واحد».' },
        { title: 'روابط لا يمكن اختلاقها.', body: 'لا يكتب الذكاء الاصطناعي الروابط أبدًا، بل يضيف خبر روابط المقالات الحقيقية بنفسه.' },
        { title: 'خبير لا يختلق الأحداث.', body: 'يوم الأحد، لا يعتمد خبير خبر الاصطناعي إلا على أخبار أرسلها لك خبر من قبل.' },
      ],
      example: {
        label: 'مثال لخبرين في ملخص',
        singleSource: 'مصدر واحد',
        items: [
          {
            title: 'الرباط تفتتح خط ترامواي جديدًا',
            summary: 'خطان جديدان يربطان الأحياء البعيدة بوسط المدينة، وفق السلطات المحلية.',
            sources: ['Hespress', 'Médias24', 'TelQuel'],
            single: false,
          },
          {
            title: 'ميناء أكادير يخطط لمحطة صيد أكبر',
            summary: 'تقول سلطة الميناء إن الأشغال قد تبدأ العام المقبل.',
            sources: ['Médias24'],
            single: true,
          },
        ],
      },
    },
    faq: {
      title: 'أسئلة شائعة',
      items: [
        { q: 'هل خبر مجاني؟', a: 'نعم، خبر مجاني.' },
        { q: 'ما المواضيع التي يغطيها؟', a: 'ستة مواضيع: السياسة الدولية، والمغرب، والاقتصاد، والتقنية والذكاء الاصطناعي، وهندسة البرمجيات، والعلوم والهندسة.' },
        { q: 'بأي لغة تصل الملخصات؟', a: 'بالإنجليزية حاليًا، والملخصات بالعربية قادمة قريبًا. ويقرأ خبر مصادر بالإنجليزية والفرنسية والعربية.' },
        { q: 'من يكتب الملخصات؟', a: 'يكتب نموذج ذكاء اصطناعي كل ملخص من المقالات التي يقرؤها خبر. ولا يكتب الروابط أبدًا، بل يضيف خبر روابط المقالات الحقيقية بنفسه.' },
        { q: 'لماذا عليّ تأكيد بريدي؟', a: 'حتى لا يسجّلك أحد دون إذنك. اضغط على الرابط الذي نرسله إليك وتبدأ الملخصات.' },
        { q: 'كيف ألغي الاشتراك؟', a: 'في أسفل كل رسالة رابط لإلغاء الاشتراك. ضغطة واحدة وتتوقف الرسائل.' },
        { q: 'ماذا تفعلون ببريدي؟', a: 'نستخدمه فقط لإرسال الملخصات إليك، ولا نبيعه ولا نشاركه أبدًا.' },
      ],
    },
    final: {
      title: 'احصل على الملخص القادم في بريدك',
      body: 'ثلاث رسائل قصيرة كل يوم، وتحليل واحد يوم الأحد. مجانًا.',
    },
    footer: {
      source: 'الشيفرة المصدرية على GitHub',
    },
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
