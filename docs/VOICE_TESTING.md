# Native voice and own-voice rehearsal

## Gemini Live

Open `/app/?live=1`, choose EN / ZH / DE / HI, then Call Pawse and consent to Gemini processing. Enable the microphone yourself. Use headphones and a fictional case: “Mimi is limping after jumping from a wardrobe.” Check the transcript, spoken response, care result, interruptibility, mute and hang-up. Repeat with representative speech in each language; model availability does not establish recognition quality.

The conversation uses Gemini native audio. It does not clone your voice. To explicitly test the older REST fallback, append `&voice=rest`.

## Record your voice and rehearse German

1. Redeem the event coupon in Gradium Studio, create an API key, and set `GRADIUM_API_KEY` in the local ignored `.env`. Restart the backend. The coupon URL is not a credential. Never commit a key or recording.
2. From the React home page choose **Record my voice · emergency rehearsal**. Record the displayed English or German passage for 10–25 seconds in a quiet room and listen locally. Recording alone does not upload audio.
3. Confirm that this is your own voice and consent to Gradium processing. Select **Clone and preview in German**. The app keeps the source ID, creates one German candidate for an English recording, checks readiness automatically, and generates a preview. If a stage fails, use **Refresh voice status** or **Continue to German preview**; do not repeatedly clone.
4. Generate and listen to the preview fully, approve it, and save the German version when requested.
5. Select **Speak the rehearsal in my voice**. Compare pronunciation, intelligibility and speaker similarity with your original. Download only if you wish to retain the sample.

The script explicitly says it is a rehearsal and that an AI assistant is speaking for the owner. It asks a vet about a fictional limping cat. It does not place a telephone call or claim an appointment. Existing policy, calendar, taxi and telephone limitations remain unchanged.

Local recording works without Gradium credentials. Clone, localization and generated own-voice audio require the key and an approved profile. The source recording stays in page memory; provider profile storage follows the existing server enrollment contract. Reloading the page loses the unsent recording.

## Where the voice goes

The source clone is stored in the authenticated Gradium organization; the page displays its ID. A localized candidate is temporary until you listen and choose **Save approved voice**, which keeps a permanent German voice in Gradium. The prototype currently associates these IDs with the browser session in server memory: a server restart loses that association, not the provider voice. Do not restart during enrollment; retain the displayed German ID for later configuration/recovery.

The clone endpoint can return an ID together with “Please wait a bit till the voice is ready to be used.” That exact pending notice is accepted only for cloning; other provider errors remain errors. Cloning has a bounded 90-second transport deadline. German preparation polls at most 20 times, three seconds apart, then offers an explicit Continue action. These bounds are not latency guarantees. Recording directly in German avoids a separate language-localization stage; English samples need it. No claim of fastest performance across providers is made.
