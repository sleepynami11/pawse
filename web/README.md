# Pawse Web（前端）

宠物不舒服时，**打给 Pawse 说说**。以语音为主，需要时再开摄像头或发照片。
Pawse 用语音回答、给出分级和下一步建议，然后先列出附近的诊所，选好后**帮你打给兽医**，也可以**帮你问保险**。

```
首页 → 语音通话（摄像头 / 照片 / 文字 / 关键词都是可选）→ 建议卡
     → 转接兽医：先看附近诊所列表 → 选一家 → Pawse 打过去（德语 + 实时翻译）
     → 转接保险：Pawse 打给保险公司
     → 总结页
```

默认是**演示模式**：对话、诊所、电话都是脚本数据，Pawse 用浏览器自带的声音读出来（电话里读德语）。
队友的三个工具放到 GitHub 后，替换下面三个“插槽”文件就能接上，可以一个一个接。

## 快速开始

```bash
npm install
npm run dev        # 浏览器打开 localhost:5173
npm run check      # 纯 Node 检查演示数据、接口契约和金额（不需要装依赖）
```

- 想演快一点：`localhost:5173/?speed=3`（倍速时不出声，只走字幕）。
- 演示里你不说话的话，几秒后 Pawse 会“听到”脚本里的回答；点关键词或打字会马上用你的输入。
- 摄像头 / 麦克风 / 定位：电脑上 `localhost` 可以直接用。手机用局域网 `http://` 打开时浏览器会拦住，需要 HTTPS（部署后就好）。打不开时界面会提示，通话照样能继续。

## 界面

| 页面 | 文件 | 内容 |
|---|---|---|
| 首页 | `src/pages/Home.jsx` | 虚拟形象 Pawse、“呼叫 Pawse” |
| 语音通话 | `src/pages/VoiceCall.jsx` | 大头像（说话时嘴会动、有光圈）；字幕；关键词；文字框 + 📷 发照片；麦克风 / 挂断 / 摄像头（可选，打开后变成小画面）；分诊后弹出建议卡 |
| 诊所列表 | `src/pages/ClinicList.jsx` | 按距离排序；营业中 / 已关门 / 急诊 / 最近；地图链接；“让 Pawse 打” |
| 转接电话 | `src/pages/PhoneCall.jsx` | 呼叫中 → 通话中；原话（德语）+ 实时翻译；结果卡 |
| 总结 | `src/pages/Plan.jsx` | 建议、已完成的电话、可复制的病情摘要、理赔材料 |

虚拟形象在 `src/components/Avatar.jsx`，颜色在 `src/styles.css` 顶部的 `:root`。

## 插槽一：语音智能体（给语音队友）

替换 `src/agents/liveVoiceAgent.js`，导出 `createLiveVoiceAgent({ lang })`：

```js
agent.on(cb)                          // 订阅事件，返回取消订阅函数
agent.start()
agent.end()                           // 必须发出一次 {type:'ended'}
agent.sendText(text)                  // 用户打字，或点了关键词
agent.sendImage(file)                 // 用户拍 / 选的照片（可选功能）
agent.attachMedia({ audio, video })   // 麦克风 MediaStream；video 只有用户打开摄像头时才有，否则 null
agent.setMicMuted(bool)
agent.wantsAudio = true               // 页面会打开麦克风
```

要发出的事件：

```js
{ type: 'transcript', role: 'user' | 'ai', text }     // 字幕
{ type: 'speaking', who: 'user' | 'ai' | 'none' }     // 控制形象的嘴和光圈
{ type: 'listening', on: true | false }               // “在听…”
{ type: 'suggestions', items: ['瘸腿', '呕吐', …] }    // 关键词（[] 隐藏）
{ type: 'image_received' }                            // 收到照片
{ type: 'triage', level: 'red'|'yellow'|'green', headline, steps: [...], escalation, summary }
{ type: 'error', message }
{ type: 'ended' }
```

AI 的声音由智能体自己播放。

## 插槽二：诊所搜索 / 地图（给搜索队友）

替换 `src/agents/liveClinicSearch.js`，导出：

```js
liveSearchClinics({ lang, location, triage })  →  Promise<{ clinics: [...] }>
```

- `location`：`{ lat, lng }`；用户不给定位时是 `null`（页面会提示“距离可能不准”）
- `triage`：Pawse 的判断，比如 `level === 'red'` 时可以优先急诊

每家诊所：

```js
{ id, name, address, distanceKm: 0.8, openNow: true,
  hoursText: '营业到 18:30', emergency: false, rating: 4.7, mapsUrl: 'https://…' }
```

页面按你返回的顺序显示；已关门的诊所不能点“让 Pawse 打”。用户选中的诊所会作为 `context.clinic` 传给插槽三。

## 插槽三：打电话智能体（给电话队友）

替换 `src/agents/livePhoneAgent.js`，导出 `createLivePhoneCall({ target, lang, context })`：

- `target`：`'vet'` 或 `'insurance'`
- `context`：`{ summary, clinic, estimate }`，分别是病情摘要、用户选的诊所（含名字和地址，电话号码可以由插槽二一起给），以及打保险时兽医给的预估价

```js
call.on(cb); call.start(); call.hangup();
```

要发出的事件：

```js
{ type: 'status', state: 'dialing' | 'connected' | 'ended' }
{ type: 'speaking', who: 'ai' | 'callee' | 'none' }
{ type: 'line', who: 'ai' | 'callee', original: '德语原话', text: '翻译' }
{ type: 'result', kind: 'appointment', time: '16:30', place, estimate: 600, currency: 'CHF', note }     // 兽医
{ type: 'result', kind: 'coverage', covered, currency, deductible, rate, estimate,
  reimbursed, outOfPocket, points: [{ ok, text, ref }] }                                            // 保险
{ type: 'error', message }
```

约定：**每通电话的第一句先说明“我是 AI 助手，代表主人来电”**。

## 切换到真实工具

在 `.env.local` 里（参考 `.env.example`），三块可以分开切：

```
VITE_VOICE_AGENT=live
VITE_VOICE_AGENT_URL=wss://…
VITE_CLINIC_SEARCH=live
VITE_CLINIC_SEARCH_URL=https://…
VITE_PHONE_AGENT=live
VITE_PHONE_AGENT_URL=wss://…
```

插槽里默认写了最简单的连接方式（语音和电话用 WebSocket，搜索用 POST）。服务端直接按上面的格式返回就能用，不一样的话改插槽文件就行。
完整定义在 `src/contracts.js`。数据格式不对时，浏览器控制台会出现 `[Pawse]` 警告，方便联调。

## 目录

```
src/
  App.jsx                 页面切换：home → voice → clinics → phone → plan
  contracts.js            三个工具的接口 + 校验
  config.js               环境开关、?speed=
  i18n.js                 中英文文案
  styles.css              樱花粉主题
  pages/                  Home / VoiceCall / ClinicList / PhoneCall / Plan
  components/             Avatar（虚拟形象）/ Icon / PlanPanel（建议卡）
  hooks/useUserMedia.js   打开麦克风 / 摄像头
  agents/
    index.js              按环境变量选演示版或真实版
    mockVoiceAgent.js     演示：语音对话
    mockClinicSearch.js   演示：诊所列表（虚构诊所，名字带 “(Demo)”）
    mockPhoneAgent.js     演示：打电话
    mockScripts.js        演示台词（中英文 + 德语）、诊所、金额
    speech.js             演示用的浏览器语音
    liveVoiceAgent.js     ← 插槽一：语音队友
    liveClinicSearch.js   ← 插槽二：搜索队友
    livePhoneAgent.js     ← 插槽三：电话队友
  utils/                  病情摘要、复制
scripts/check-agents.mjs  纯 Node 检查
```

## 注意

- 演示台词、诊所和金额都是**占位内容**，不是兽医或保险建议，诊所是虚构的。德语请找会德语的人看一眼。
- 演示里的电话是脚本，没有真的打出去。真的外呼要先让用户确认，并符合当地的录音和 AI 来电规定。
