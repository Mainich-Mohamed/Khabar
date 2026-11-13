export const strings = {
  en: {
    wordmark: 'Khabar',
    languageGroup: 'Language',
    home: 'Khabar, back to top',
    hero: {
      tagline: 'The news, read for you',
      headline: 'Three short news emails a day. Every source linked',
      subheadline:
        'Khabar reads 33 trusted outlets, merges the stories about the same event, and sends you a short brief. No app, no scrolling',
    },
    outlets: { title: 'Khabar reads these outlets, and more' },
    what: {
      title: 'What you get',
      stops: [
        { time: '07:00', name: 'Morning brief', body: 'The top story first, then every topic in a few lines, with sources' },
        { time: '16:00', name: 'Afternoon update', body: "Only what's new since the morning" },
        { time: '20:00', name: 'Evening brief', body: "The day in full, without repeating this morning's stories" },
        { time: 'Sunday 20:30', name: 'Khabar Artificial Expert', body: 'It rereads everything Khabar sent you that week, and explains what it means' },
      ],
    },
    trust: {
      title: 'Why you can trust it',
      points: [
        { title: 'One event, one story', body: 'When five outlets cover the same event, you read it once, with all five links' },
        { title: 'Facts only from the articles', body: 'An AI writes each summary from the articles themselves. A story only one outlet reports is marked single source' },
        { title: "Links that can't be made up", body: 'The AI never writes links. Khabar attaches the real article links itself' },
        { title: "An expert that can't invent events", body: 'On Sunday, the Khabar Artificial Expert works only from stories Khabar already sent you' },
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
        { q: 'Is Khabar free ?', a: 'Yes. Khabar is free' },
        { q: 'Which topics does it cover ?', a: 'Six: geopolitics, Morocco, economy, tech and AI, software engineering, and science and engineering' },
        { q: 'Which language are the briefs in ?', a: 'English for now. Arabic briefs are coming soon. Khabar reads outlets in English, French and Arabic' },
        { q: 'Who writes the briefs ?', a: 'An AI model writes each summary from the articles Khabar reads. It never writes the links: Khabar attaches the real article links itself' },
        { q: 'Why do I need to confirm my email ?', a: 'So no one can sign you up without asking you. Tap the link we send you and the briefs start' },
        { q: 'How do I unsubscribe ?', a: 'Every email has an unsubscribe link at the bottom. One tap and the emails stop' },
        { q: 'What do you do with my email ?', a: 'We use it only to send you the briefs. We never sell or share it' },
      ],
    },
    final: {
      title: 'Get the next brief in your inbox',
      body: 'Three short emails a day, and one analysis on Sunday. 100% Free.',
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
      tagline: 'نقرأ الأخبار بدلًا منك',
      headline: 'ثلاث رسائل إخبارية قصيرة في اليوم، ولكل خبر رابط مصدره',
      subheadline: 'نقرأ 33 مصدرًا موثوقًا، ونضمّ ما يُنشر عن الحدث الواحد في خبر واحد، ثم نرسل إليك ملخصًا قصيرًا. بلا تطبيق وبلا سكرول',
    },
    outlets: { title: 'يقرأ خبر هذه المصادر وغيرها' },
    what: {
      title: 'ما يصلك',
      stops: [
        { time: '07:00', name: 'ملخص الصباح', body: 'أهم خبر في البداية، ثم بقية المواضيع في أسطر قليلة مع مصادرها' },
        { time: '16:00', name: 'مستجدّات بعد الظهر', body: 'ما استجدّ منذ الصباح فقط' },
        { time: '20:00', name: 'ملخص المساء', body: 'حصيلة اليوم كاملة، دون تكرار ما قرأته صباحًا' },
        { time: 'الأحد 20:30', name: 'خبير خبر الاصطناعي', body: 'يعيد قراءة كل ما أرسلناه إليك خلال الأسبوع، ويشرح لك دلالته' },
      ],
    },
    trust: {
      title: 'لماذا تثق بنا',
      points: [
        { title: 'خبر واحد لكل حدث', body: 'إذا غطّت خمسة مصادر الحدث نفسه، قرأته مرة واحدة ومعه روابطها الخمسة' },
        { title: 'لا معلومة من خارج المقالات', body: 'يكتب الذكاء الاصطناعي كل ملخص اعتمادًا على المقالات وحدها، وإذا انفرد مصدر واحد بخبر، أشرنا إليه بعبارة «مصدر واحد»' },
        { title: 'روابط لا مجال لاختلاقها', body: 'لا يكتب الذكاء الاصطناعي أي رابط، بل نضيف نحن روابط المقالات الأصلية' },
        { title: 'خبير لا يختلق الأحداث', body: 'يوم الأحد، لا يعتمد خبير خبر الاصطناعي إلا على أخبار سبق أن أرسلناها إليك' },
      ],
      example: {
        label: 'مثال: خبران كما يظهران في الملخص',
        singleSource: 'مصدر واحد',
        items: [
          {
            title: 'الرباط تفتتح خط ترامواي جديدًا',
            summary: 'خطان جديدان يربطان الأحياء البعيدة بوسط المدينة، وفق السلطات المحلية.',
            sources: ['Hespress', 'Médias24', 'TelQuel'],
            single: false,
          },
          {
            title: 'ميناء أكادير يعتزم إنشاء محطة صيد أكبر',
            summary: 'تقول إدارة الميناء إن الأشغال قد تنطلق العام المقبل.',
            sources: ['Médias24'],
            single: true,
          },
        ],
      },
    },
    faq: {
      title: 'أسئلة شائعة',
      items: [
        { q: 'هل الاشتراك في خبر مجاني؟', a: 'نعم، مجاني تمامًا' },
        { q: 'ما المواضيع التي يغطيها؟', a: 'ستة مواضيع: السياسة الدولية، والمغرب، والاقتصاد، والتقنية والذكاء الاصطناعي، وهندسة البرمجيات، والعلوم والهندسة' },
        { q: 'بأي لغة تصل الملخصات؟', a: 'بالإنجليزية حاليًا، وستصدر بالعربية قريبًا. أما المصادر فبالإنجليزية والفرنسية والعربية' },
        { q: 'من يكتب الملخصات؟', a: 'يكتبها نموذج ذكاء اصطناعي اعتمادًا على المقالات التي نجمعها، لكنه لا يكتب الروابط، بل نضيف نحن روابط المقالات الأصلية' },
        { q: 'لماذا عليّ تأكيد بريدي؟', a: 'حتى لا يسجّلك أحد دون إذنك. اضغط على الرابط الذي سنرسله إليك، وتصلك الملخصات بعدها' },
        { q: 'كيف ألغي الاشتراك؟', a: 'في أسفل كل رسالة رابط لإلغاء الاشتراك. ضغطة واحدة وتتوقف الرسائل' },
        { q: 'ماذا تفعلون ببريدي؟', a: 'لا نستخدمه إلا لإرسال الملخصات إليك، ولا نبيعه ولا نشاركه مع أحد' },
      ],
    },
    final: {
      title: 'ليصلك الملخص القادم إلى بريدك',
      body: 'ثلاث رسائل قصيرة في اليوم، وتحليل كل أحد. مجانًا بالكامل.',
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
      successBody: 'أرسلنا إليك رابطًا، اضغط عليه ليبدأ وصول الملخصات. إن لم تجده، فابحث في مجلد الرسائل غير المرغوب فيها.',
      successArabic: 'ستصدر الملخصات بالعربية قريبًا، وسنرسلها إليك حين تجهز.',
      errors: {
        invalid: 'أدخل بريدًا إلكترونيًا كاملًا، مثل \u2066name@example.com\u2069.',
        network: 'تعذّر الاتصال. تحقّق من اتصالك بالإنترنت وحاول مرة أخرى.',
      },
    },
  },
} as const
