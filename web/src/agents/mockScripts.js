// Scripted demo content for the mock agents ("Mimi is limping, Zurich, you don't speak German").
// PLACEHOLDER content to drive the UI. It is not veterinary or insurance advice.

const T = (en, zh) => ({ en, zh });

/** If the user doesn't answer, the mock "hears" a scripted answer after this long. */
export const AUTO_REPLY_MS = 7000;

// ------------------------------------------------------------- voice agent
export const voiceScript = {
  greet: T(
    "Hi, I'm Pawse. Tell me what happened. If it helps, you can turn on the camera or send me a photo.",
    '嗨，我是 Pawse。告诉我发生了什么？需要的话，也可以开摄像头或者发张照片给我。'
  ),
  chips0: {
    zh: ['走路一瘸一拐', '一直呕吐', '不吃东西', '可能误食', '呼吸很急'],
    en: ['Limping', 'Vomiting', 'Not eating', 'Swallowed something', 'Breathing fast'],
  },
  user1: T('My cat is limping, please help me.', '我的猫走路一瘸一拐的，请帮帮我。'),
  ask: T(
    'Okay. Did she fall, or did she jump down from somewhere high?',
    '好的。它是摔下来的，还是自己从高处跳下来的？'
  ),
  chips1: {
    zh: ['从衣柜上跳下来', '摔下来的', '不确定'],
    en: ['Jumped off the wardrobe', 'She fell', 'Not sure'],
  },
  user2: T('She jumped off the wardrobe.', '它从衣柜上跳下来的。'),
  photoThanks: T('Got the photo, thank you.', '收到照片了，谢谢。'),
  verdict: T(
    "Sounds like she hurt herself landing. She should see a vet today. Keep her in the carrier so she moves less, and don't massage the leg. I can call the nearest open practice for you, and check what your insurance covers.",
    '听起来是落地时受了伤，今天就该让兽医看看。先让它待在航空箱里少走动，不要按揉那条腿。我可以帮你打给最近营业的诊所，也可以问问保险能赔多少。'
  ),
  triage: {
    level: 'yellow',
    headline: T('See a vet today', '今天就诊'),
    steps: {
      zh: ['让它待在航空箱里，少走动', '不要按揉或拉伸那条腿', '不要喂人用的止痛药'],
      en: ['Keep her in the carrier so she moves less', "Don't massage or stretch the leg", "Don't give human painkillers"],
    },
    escalation: T(
      "If she can't put the leg down at all, it swells quickly, or she keeps crying: go to a vet now.",
      '如果那条腿完全不能着地、肿得很快，或者一直叫：立刻就医。'
    ),
    summary: T(
      'Cat: Mimi\nProblem: limping since jumping off a wardrobe today (accident)\nAI triage: see a vet today\nNote: owner-reported, not a diagnosis.',
      '猫：咪咪（Mimi）\n问题：今天从衣柜上跳下后走路一瘸一拐（意外）\nAI 分诊：今天就诊\n※ 主人口述整理，非诊断。'
    ),
  },
};

// ------------------------------------------------------------- phone agent
// `de` is what is actually said on the call (Zurich); `text` is the translation for the transcript.
// The owner never has to read German: `step` is the plain-language progress shown while the call
// runs, and a `question` pauses the call until the owner decides (the answer picks a branch).
export const phoneScripts = {
  vet: {
    lines: [
      {
        who: 'ai',
        step: T('Introduced itself as an AI and explained what happened to Mimi', '说明自己是 AI，并讲了 Mimi 的情况'),
        de: 'Guten Tag, hier ist Pawse, ein KI-Assistent. Ich rufe im Auftrag einer Katzenbesitzerin an. Ihre Katze humpelt, seit sie heute vom Schrank gesprungen ist. Haben Sie heute noch einen Termin frei?',
        text: T(
          "Hello, this is Pawse, an AI assistant calling on behalf of a cat owner. Her cat has been limping since jumping off a wardrobe today. Do you have an appointment free today?",
          '您好，我是 Pawse，一个 AI 助手，代表一位猫主人来电。她的猫今天从衣柜上跳下来后一直瘸腿。请问今天还有空位吗？'
        ),
      },
      {
        who: 'callee',
        step: T('The practice offered 16:30 today, or a home visit this evening', '诊所可以今天 16:30 看，或者今晚上门'),
        de: 'Ja, um 16:30 Uhr hätte ich Platz in der Praxis. Oder ich komme heute Abend für einen Hausbesuch.',
        text: T('Yes, I have a slot at 4:30 pm at the practice. Or I can do a home visit this evening.', '有的，下午 4:30 诊所有空位。或者我今晚可以上门。'),
      },
      {
        question: {
          id: 'slot',
          text: T(
            'The practice can see Mimi at 16:30 today, or the vet can come to your home this evening. Which do you prefer?',
            '诊所今天 16:30 可以看 Mimi，或者兽医今晚上门。你选哪个？'
          ),
          options: [
            { id: 'practice', label: T('16:30 at the practice', '16:30 去诊所') },
            { id: 'home', label: T('Home visit this evening', '今晚上门') },
          ],
          fallback: 'practice',
        },
        branches: {
          practice: [
            {
              who: 'ai',
              step: T('Took the 16:30 slot and asked about the cost', '定了 16:30，并问了费用'),
              de: '16:30 Uhr in der Praxis passt. Was kostet die Behandlung ungefähr?',
              text: T('4:30 pm at the practice works. Roughly what will it cost?', '4:30 去诊所可以。大概要多少钱？'),
            },
            {
              who: 'callee',
              de: 'Mit Untersuchung und Behandlung rechnen Sie mit etwa 600 Franken. Ein Hausbesuch kostet 150 Franken zusätzlich.',
              text: T('With the examination and treatment, about 600 francs. A home visit is 150 francs extra.', '检查加治疗大约 600 瑞郎。上门另加 150 瑞郎。'),
            },
            {
              who: 'ai',
              step: T('Confirmed and asked for an itemised invoice for your claim', '确认预约，并要了理赔用的明细发票'),
              de: 'Perfekt, dann bis 16:30 Uhr. Bitte stellen Sie eine detaillierte Rechnung aus. Vielen Dank!',
              text: T('Perfect, see you at 4:30 pm. Please issue an itemised invoice. Thank you!', '好的，那 4:30 见。请开具明细发票，谢谢！'),
            },
            {
              who: 'callee',
              de: 'Gerne, bis später.',
              text: T('You are welcome, see you later.', '不客气，待会见。'),
            },
          ],
          home: [
            {
              who: 'ai',
              step: T('Asked for the home visit and the cost', '要了上门看诊，并问了费用'),
              de: 'Dann bitte den Hausbesuch heute Abend. Was kostet das ungefähr?',
              text: T('Then the home visit this evening, please. Roughly what will it cost?', '那就今晚上门吧。大概要多少钱？'),
            },
            {
              who: 'callee',
              de: 'Mit Untersuchung und Behandlung rechnen Sie mit etwa 600 Franken. Der Hausbesuch kostet 150 Franken zusätzlich.',
              text: T('With the examination and treatment, about 600 francs. The home visit is 150 francs extra.', '检查加治疗大约 600 瑞郎。上门另加 150 瑞郎。'),
            },
            {
              who: 'ai',
              step: T('Confirmed and asked for an itemised invoice for your claim', '确认预约，并要了理赔用的明细发票'),
              de: 'Perfekt, dann bis heute Abend. Bitte stellen Sie eine detaillierte Rechnung aus. Vielen Dank!',
              text: T('Perfect, see you this evening. Please issue an itemised invoice. Thank you!', '好的，那今晚见。请开具明细发票，谢谢！'),
            },
            {
              who: 'callee',
              de: 'Gerne, bis heute Abend.',
              text: T('You are welcome, see you this evening.', '不客气，今晚见。'),
            },
          ],
        },
      },
    ],
  },
  insurance: {
    lines: [
      {
        who: 'ai',
        step: T('Introduced itself as an AI and explained the accident and the CHF 600 estimate', '说明自己是 AI，讲了意外和 600 瑞郎的预估'),
        de: 'Guten Tag, hier ist Pawse, ein KI-Assistent im Auftrag einer Versicherten. Ihre Katze hatte heute einen Unfall, der Tierarzt schätzt etwa 600 Franken. Ist das gedeckt?',
        text: T(
          "Hello, this is Pawse, an AI assistant calling on behalf of a policyholder. Her cat had an accident today; the vet estimates about 600 francs. Is that covered?",
          '您好，我是 Pawse，一个 AI 助手，代表一位投保人来电。她的猫今天出了意外，兽医预估约 600 瑞郎。这个能赔吗？'
        ),
      },
      {
        who: 'callee',
        step: T('Accident covered: CHF 300 excess, then 80% back', '意外能赔：免赔 300 瑞郎，之后报销 80%'),
        de: 'Ja, Unfälle sind ab dem ersten Tag gedeckt. Der Selbstbehalt beträgt 300 Franken, danach erstatten wir 80 Prozent.',
        text: T('Yes, accidents are covered from day one. The excess is 300 francs, after that we reimburse 80 percent.', '能赔。意外从第一天起就保。免赔额 300 瑞郎，超出部分报销 80%。'),
      },
      {
        who: 'ai',
        step: T('Asked about a home visit and physio', '问了上门和理疗'),
        de: 'Und ein Hausbesuch oder Physiotherapie danach?',
        text: T('And a home visit, or physiotherapy afterwards?', '那上门看诊，或者之后的理疗呢？'),
      },
      {
        who: 'callee',
        step: T('Home visit and physio are not covered (AVB 1.2.5, 1.2.6)', '上门和理疗都不保（AVB 1.2.5、1.2.6）'),
        de: 'Der Hausbesuch ist in Ihrem Tarif nicht gedeckt, siehe AVB 1.2.5. Physiotherapie ebenfalls nicht, siehe AVB 1.2.6.',
        text: T("The home visit isn't covered on this plan, see AVB 1.2.5. Physiotherapy isn't either, see AVB 1.2.6.", '你的方案不保上门费，见条款 AVB 1.2.5。理疗也不保，见 AVB 1.2.6。'),
      },
      {
        who: 'ai',
        de: 'Verstanden, vielen Dank für die Auskunft.',
        text: T('Understood, thank you for the information.', '明白了，谢谢您的说明。'),
      },
    ],
  },
};

export const INSURANCE_RULES = { deductible: 300, rate: 0.8 };
export const DEFAULT_ESTIMATE = 600;

/** What the insurer pays back: rate × everything above the deductible. */
export function reimbursement(total, { deductible, rate } = INSURANCE_RULES) {
  return Math.round(Math.max(0, total - deductible) * rate);
}

export const HOME_VISIT_FEE = 150;

/** `choice` is the owner's answer to the slot question: 'practice' (default) or 'home'. */
export function buildVetResult(lang, clinic, choice = 'practice') {
  const L = (o) => o[lang] ?? o.en;
  const place = clinic && clinic.name ? clinic.name : L(T('Vet practice (nearest open)', '兽医诊所（最近营业）'));
  if (choice === 'home') {
    return {
      kind: 'appointment',
      time: L(T('This evening', '今晚')),
      place: `${L(T('Home visit', '上门'))} · ${place}`,
      estimate: DEFAULT_ESTIMATE + HOME_VISIT_FEE,
      homeVisitFee: HOME_VISIT_FEE,
      currency: 'CHF',
      note: L(T('Includes CHF 150 for the home visit', '含上门费 CHF 150')),
    };
  }
  return {
    kind: 'appointment',
    time: '16:30',
    place,
    estimate: DEFAULT_ESTIMATE,
    currency: 'CHF',
    note: L(T('Home visit would be + CHF 150', '上门另加 CHF 150')),
  };
}

/** `homeVisitFee` is part of `estimate` but never reimbursed (AVB 1.2.5). */
export function buildInsuranceResult(lang, estimate = DEFAULT_ESTIMATE, homeVisitFee = 0) {
  const L = (o) => o[lang] ?? o.en;
  const reimbursed = reimbursement(estimate - homeVisitFee);
  return {
    kind: 'coverage',
    covered: true,
    currency: 'CHF',
    ...INSURANCE_RULES,
    estimate,
    reimbursed,
    outOfPocket: estimate - reimbursed,
    points: [
      { ok: true, text: L(T('Accident covered from day 1', '意外从第一天起就保')) },
      { ok: true, text: L(T('You pay the first CHF 300, then 80% is reimbursed', '你先付前 300 瑞郎，之后报销 80%')) },
      { ok: false, text: L(T('Home visit not covered', '上门费不保')), ref: 'AVB 1.2.5' },
      { ok: false, text: L(T('Physio afterwards not covered', '之后的理疗不保')), ref: 'AVB 1.2.6' },
    ],
  };
}

// ------------------------------------------------------------- clinic search
// Fictional clinics for the demo (names end in "(Demo)" on purpose).
export const demoClinics = [
  {
    id: 'demo-limmat',
    name: 'Tierarztpraxis Limmatblick (Demo)',
    address: 'Limmatquai 1, 8001 Zürich',
    distanceKm: 0.8,
    openNow: true,
    hoursText: T('Open until 18:30', '营业到 18:30'),
    rating: 4.7,
  },
  {
    id: 'demo-zuerichberg',
    name: 'Kleintierpraxis Zürichberg (Demo)',
    address: 'Bergstrasse 10, 8032 Zürich',
    distanceKm: 1.6,
    openNow: true,
    hoursText: T('Open until 19:00', '营业到 19:00'),
    rating: 4.5,
  },
  {
    id: 'demo-notfall',
    name: 'Notfall-Tierklinik West (Demo)',
    address: 'Badenerstrasse 300, 8004 Zürich',
    distanceKm: 3.9,
    openNow: true,
    emergency: true,
    hoursText: T('Emergency 24/7', '24 小时急诊'),
    rating: 4.3,
  },
  {
    id: 'demo-altstetten',
    name: 'Tierarztpraxis Altstetten (Demo)',
    address: 'Altstetterstrasse 50, 8048 Zürich',
    distanceKm: 4.4,
    openNow: false,
    hoursText: T('Closed · opens tomorrow 08:00', '已关门 · 明天 08:00 开'),
    rating: 4.6,
  },
];
