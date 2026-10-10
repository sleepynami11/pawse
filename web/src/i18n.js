export const LANGS = ['zh', 'en', 'de', 'hi'];

export const strings = {
  zh: {
    appName: 'Pawse',
    tagline: '宠物不舒服？\n跟 Pawse 说说。',
    startCall: '呼叫 Pawse',
    startHint: '直接说话就行，需要时再开摄像头或发照片',
    mockBadge: '演示模式 · 脚本数据',
    disclaimer: 'Pawse 给的是分诊建议，不是诊断，不能替代兽医。情况危急请直接去医院。',

    connecting: '接通中…',
    listening: '在听…',
    aiSpeaking: '正在说话',
    you: '你',
    typePlaceholder: '也可以打字…',
    send: '发送',
    camUnavailable: '没能打开摄像头，可以继续用语音、照片或文字。',
    micUnavailable: '没能打开麦克风，可以先用文字或关键词。',
    camOff: '摄像头已关闭',
    camOpening: '正在打开摄像头…',
    photo: '发照片',
    photoSent: '照片已发给 Pawse',
    closeCamera: '关闭摄像头',
    mic: '麦克风',
    camera: '摄像头',
    flip: '翻转',
    hangup: '挂断',
    sound: 'Pawse 的声音',
    gradiumVoice: '用 Gradium 德语声音说话',
    gradiumOwnVoice: '用你自己的声音说德语（Gradium）',
    gradiumNote: 'Pawse 说的德语句子会发送给 Gradium 生成语音。关闭后使用浏览器自带的声音。',
    viewAdvice: '查看建议',
    keepTalking: '继续通话',

    adviceTitle: 'Pawse 的建议',
    nowDo: '现在可以做',
    transferTitle: '让 Pawse 帮你打电话',
    aiNote: 'Pawse 会先说明自己是 AI 助手，代表你来电。',
    callVet: '转接兽医',
    callVetSub: '先看看附近的诊所，再让 Pawse 打过去',
    callIns: '转接保险',
    callInsSub: '问清楚能赔多少',
    call: '转接',
    callAgain: '再打',
    booked: '已预约',
    outOfPocket: '预计自付',
    done: '完成',

    dialing: '呼叫中…',
    inCall: '通话中',
    callEnded: '通话结束',
    liveTranslate: '德语 · 实时翻译',
    pawse: 'Pawse',
    appointment: '已预约',
    estimate: '预估费用',
    simulated: '模拟（演示）',
    insuranceAnswer: '保险怎么说',
    reimbursed: '预计报销',
    backToPawse: '回到 Pawse',

    clinicsTitle: '选一家诊所',
    clinicsSub: '按距离排序 · 选好后 Pawse 帮你打过去',
    clinicsLoading: '正在找附近营业的诊所…',
    clinicsError: '暂时没找到诊所。',
    retry: '再试一次',
    back: '返回',
    openNow: '营业中',
    closed: '已关门',
    emergency24: '急诊',
    nearest: '最近',
    map: '地图',
    callThis: '让 Pawse 打',
    noLocation: '没有用到你的位置，距离可能不准。',

    planTitle: '都在这里了',
    summary: '病情摘要',
    copy: '复制',
    copied: '已复制',
    checklistTitle: '理赔要留的材料',
    checklist: ['保留刚才的视频', '找诊所要明细发票', '保留病历和付款凭证', '30 天内提交理赔'],
    restart: '重新开始',

    levels: { red: '立刻就医', yellow: '今天就诊', green: '居家观察' },
    callees: {
      vet: { icon: '🏥', name: '兽医诊所', role: '最近营业中' },
      insurance: { icon: '🛡️', name: '宠物保险', role: '理赔热线' },
    },
  },

  en: {
    appName: 'Pawse',
    tagline: 'Pet not well?\nTalk to Pawse.',
    startCall: 'Call Pawse',
    startHint: 'Just talk. Turn on the camera or send a photo if it helps.',
    mockBadge: 'Demo mode · scripted',
    disclaimer:
      'Pawse gives triage guidance, not a diagnosis, and does not replace a vet. In an emergency, go to a clinic.',

    connecting: 'Connecting…',
    listening: 'Listening…',
    aiSpeaking: 'Speaking',
    you: 'You',
    typePlaceholder: 'Or type here…',
    send: 'Send',
    camUnavailable: "Couldn't open the camera. You can keep going by voice, photo or text.",
    micUnavailable: "Couldn't open the microphone. You can type or tap a keyword for now.",
    camOff: 'Camera off',
    camOpening: 'Opening camera…',
    photo: 'Send photo',
    photoSent: 'Photo sent to Pawse',
    closeCamera: 'Turn camera off',
    mic: 'Microphone',
    camera: 'Camera',
    flip: 'Flip',
    hangup: 'Hang up',
    sound: "Pawse's voice",
    gradiumVoice: 'Speak with the Gradium German voice',
    gradiumOwnVoice: 'Speak German in your own voice (Gradium)',
    gradiumNote: "Pawse's German lines are sent to Gradium to make the audio. Off: the browser's built-in voice.",
    viewAdvice: 'View advice',
    keepTalking: 'Keep talking',

    adviceTitle: "Pawse's advice",
    nowDo: 'Right now',
    transferTitle: 'Let Pawse make the calls',
    aiNote: 'Pawse always says it is an AI assistant calling on your behalf.',
    callVet: 'Call the vet',
    callVetSub: 'Pick a nearby clinic, Pawse calls it',
    callIns: 'Call the insurer',
    callInsSub: "Find out what's covered",
    call: 'Call',
    callAgain: 'Again',
    booked: 'Booked',
    outOfPocket: 'You pay about',
    done: 'Done',

    dialing: 'Calling…',
    inCall: 'In call',
    callEnded: 'Call ended',
    liveTranslate: 'German · live translation',
    pawse: 'Pawse',
    appointment: 'Appointment booked',
    estimate: 'Estimate',
    simulated: 'simulated',
    insuranceAnswer: 'What the insurer said',
    reimbursed: 'Expected back',
    backToPawse: 'Back to Pawse',

    clinicsTitle: 'Pick a clinic',
    clinicsSub: 'Sorted by distance · Pawse calls the one you pick',
    clinicsLoading: 'Finding open clinics nearby…',
    clinicsError: "Couldn't find clinics right now.",
    retry: 'Try again',
    back: 'Back',
    openNow: 'Open',
    closed: 'Closed',
    emergency24: 'Emergency',
    nearest: 'Nearest',
    map: 'Map',
    callThis: 'Pawse, call',
    noLocation: "Your location wasn't used, so distances may be off.",

    planTitle: "Here's everything",
    summary: 'Case summary',
    copy: 'Copy',
    copied: 'Copied',
    checklistTitle: 'Keep for the claim',
    checklist: [
      'Keep the video you just filmed',
      'Ask the clinic for an itemised invoice',
      'Keep the medical record and proof of payment',
      'Submit the claim within 30 days',
    ],
    restart: 'Start over',

    levels: { red: 'Go to a vet now', yellow: 'See a vet today', green: 'Monitor at home' },
    callees: {
      vet: { icon: '🏥', name: 'Vet practice', role: 'Nearest open' },
      insurance: { icon: '🛡️', name: 'Pet insurer', role: 'Claims hotline' },
    },
  },
};

export function detectLang() {
  try {
    const saved = localStorage.getItem('pawse.lang');
    if (saved && LANGS.includes(saved)) return saved;
  } catch {
    /* storage unavailable */
  }
  const nav = typeof navigator !== 'undefined' ? navigator.language || '' : '';
  return nav.toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

export function saveLang(lang) {
  try {
    localStorage.setItem('pawse.lang', lang);
  } catch {
    /* ignore */
  }
}
