(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const make = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const say = (id, text) => {
    const target = byId(id);
    if (target) target.textContent = text;
  };
  const urls = new Map();
  const recordings = { sample: null, message: null };
  let profile = {},
    working = false,
    recorder = null,
    audioBusy = false,
    scriptLines = [];
  let demo = null,
    scene = 0,
    reviewedSlot = false,
    choice = null,
    confirmed = false;
  function attachAudio(player, blob, download) {
    const previous = urls.get(player.id);
    if (previous) URL.revokeObjectURL(previous);
    const url = URL.createObjectURL(blob);
    urls.set(player.id, url);
    player.src = url;
    player.hidden = false;
    if (download) {
      download.href = url;
      download.hidden = false;
    }
  }
  function clearAudio(player) {
    player.pause();
    player.removeAttribute("src");
    player.hidden = true;
    if (urls.has(player.id)) URL.revokeObjectURL(urls.get(player.id));
    urls.delete(player.id);
  }
  async function api(path, data, options = {}) {
    const response = await fetch("/api/v1/voice/" + path, {
      method: options.method || (data ? "POST" : "GET"),
      ...(data
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }
        : {}),
      signal: AbortSignal.timeout(65000),
    });
    if (!response.ok) {
      let body;
      try {
        body = await response.json();
      } catch {}
      throw Error(
        typeof body?.detail === "string"
          ? body.detail
          : body?.error?.fields?.map((x) => x.message).join("; ") ||
              "This request could not be completed. Check the recording or message and try again.",
      );
    }
    if (options.audio) return response.blob();
    return response.status === 204 ? null : response.json();
  }
  function requireChecked(id, message) {
    if (!byId(id).checked) throw Error(message);
  }
  function updateProfile(value) {
    if (value) profile = value;
    const configured = profile.gradium_configured;
    const locked = working || audioBusy || Boolean(recorder);
    const service = byId("voice-service-status");
    service.classList.toggle(
      "ready",
      Boolean(configured && profile.gemini_configured),
    );
    service.textContent = configured
      ? `Gradium configured · ${profile.my_voice_ready ? "Your German voice is ready" : "Set up your own voice below"}. ${profile.gemini_configured ? "Gemini is ready for multilingual messages." : "Gemini needs configuration for translation."}`
      : `Record and listen locally now. Add GRADIUM_API_KEY to the server’s .env and restart to enable cloning and German audio. ${profile.gemini_configured ? "Gemini is ready for multilingual transcription and scripts." : "Gemini also needs configuration."}`;
    byId("voice-profile").hidden = !profile.source_id;
    byId("clone-voice").disabled =
      locked || !configured || !recordings.sample || Boolean(profile.source_id);
    byId("localize-voice").hidden = Boolean(
      profile.german_voice_id || profile.candidate_pending,
    );
    byId("localize-voice").disabled = locked;
    byId("check-voice").hidden =
      !profile.candidate_pending || profile.candidate_ready;
    byId("check-voice").disabled = locked;
    byId("preview-voice").disabled =
      locked || !(profile.german_voice_id || profile.candidate_ready);
    byId("save-voice").hidden =
      !profile.candidate_ready || Boolean(profile.german_voice_id);
    byId("save-voice").disabled = locked || !byId("preview-listened").checked;
    byId("delete-voice").disabled = locked;
    byId("transcribe-message").disabled =
      locked || !recordings.message || !profile.gemini_configured;
    byId("prepare-script").disabled = locked || !profile.gemini_configured;
    byId("speak-script").disabled =
      locked || !scriptLines.length || !configured;
    byId("copy-script").disabled = !scriptLines.length;
    byId("saved-voice-details").hidden = !profile.german_voice_id;
    byId("saved-voice-id").textContent = profile.german_voice_id
      ? `GRADIUM_VOICE_ID_DE=${profile.german_voice_id}`
      : "";
    recordingControls();
  }
  async function task(statusId, pending, fn) {
    if (working || audioBusy || recorder) {
      say(
        statusId,
        audioBusy || recorder
          ? "Finish recording and wait for the local preview before starting a voice request."
          : "Please wait for the current voice request to finish.",
      );
      return;
    }
    working = true;
    updateProfile();
    say(statusId, pending);
    try {
      await fn();
    } catch (error) {
      say(
        statusId,
        error.name === "TimeoutError"
          ? "This request took too long. Check service status before retrying."
          : error.message,
      );
    } finally {
      working = false;
      updateProfile();
    }
  }
  async function refreshProfile() {
    updateProfile(await api("status"));
  }
  const consent = () => {
    requireChecked(
      "gradium-consent",
      "Please confirm sharing your voice with Gradium first.",
    );
    return { share_with_gradium: true };
  };
  function resetPreview() {
    clearAudio(byId("voice-preview"));
    byId("listened-label").hidden = true;
    byId("preview-listened").checked = false;
    byId("preview-listened").disabled = true;
  }
  function samplePrompt() {
    byId("sample-prompt").textContent =
      byId("sample-language").value === "de"
        ? "Hallo, ich nehme meine eigene Stimme für Pawse auf. Meine Katze ist mir sehr wichtig. Ich möchte der Tierarztpraxis ruhig erklären, was passiert ist, und alle nächsten Schritte verstehen. Bitte beziehen Sie mich bei jeder Entscheidung mit ein."
        : "Hello, I am recording my own voice for Pawse. My cat means a lot to me, and I want to explain what happened clearly. Please help me prepare for a conversation with the vet, and keep me involved in every decision.";
  }
  byId("sample-language").addEventListener("change", samplePrompt);
  async function encodeWav(blob, kind) {
    if (blob.size > 15_000_000)
      throw Error("Choose a recording smaller than 15 MB.");
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx || !window.OfflineAudioContext)
      throw Error(
        "Audio conversion is unavailable in this browser. Try a current desktop browser.",
      );
    const context = new AudioCtx();
    let decoded;
    try {
      decoded = await context.decodeAudioData(await blob.arrayBuffer());
    } finally {
      await context.close();
    }
    const min = kind === "sample" ? 10 : 0.5;
    const max = kind === "sample" ? 30 : 60;
    if (decoded.duration < min || decoded.duration > max)
      throw Error(
        `Use ${min}–${max} seconds of audio. This recording is ${decoded.duration.toFixed(1)} seconds.`,
      );
    const rate = 24000;
    const offline = new OfflineAudioContext(
      1,
      Math.ceil(decoded.duration * rate),
      rate,
    );
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const samples = (await offline.startRendering()).getChannelData(0);
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const word = (offset, text) =>
      [...text].forEach((char, i) =>
        view.setUint8(offset + i, char.charCodeAt(0)),
      );
    word(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    word(8, "WAVE");
    word(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    word(36, "data");
    view.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
      const v = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
    }
    const wav = new Blob([buffer], { type: "audio/wav" });
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(wav);
    });
    return { data, wav, duration: decoded.duration };
  }
  async function acceptRecording(blob, kind, fromRecorder = false) {
    if (working || (audioBusy && !fromRecorder)) {
      say(
        `${kind}-status`,
        "Wait for the current voice request or recording to finish before replacing the audio.",
      );
      return;
    }
    audioBusy = true;
    recordings[kind] = null;
    clearAudio(byId(`${kind}-player`));
    if (kind === "sample") byId("sample-clear").hidden = true;
    updateProfile();
    say(
      `${kind}-status`,
      "Preparing a local preview. The previous recording has been removed…",
    );
    try {
      const audio = await encodeWav(blob, kind);
      recordings[kind] = { data: audio.data };
      attachAudio(byId(`${kind}-player`), audio.wav);
      say(
        `${kind}-status`,
        `${audio.duration.toFixed(1)} seconds · only in this browser. Listen before ${kind === "sample" ? "cloning" : "transcribing"}.`,
      );
      if (kind === "sample") byId("sample-clear").hidden = false;
    } catch (error) {
      say(
        `${kind}-status`,
        `${error.message} No recording is selected; record or upload a new one.`,
      );
    } finally {
      audioBusy = false;
      updateProfile();
    }
  }
  function recordingControls() {
    for (const kind of ["sample", "message"]) {
      byId(`${kind}-record`).disabled =
        working || Boolean(audioBusy && recorder?.kind !== kind);
      byId(`${kind}-upload`).disabled = working || audioBusy;
    }
    byId("sample-language").disabled = working || audioBusy;
    byId("sample-clear").disabled = working || audioBusy;
  }
  async function record(kind) {
    if (recorder) {
      if (recorder.kind === kind && recorder.media.state === "recording")
        recorder.media.stop();
      return;
    }
    if (working || audioBusy) {
      say(
        `${kind}-status`,
        "Wait for the current voice request or local audio conversion to finish.",
      );
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      say(
        `${kind}-status`,
        "Microphone recording is unavailable. Upload a short audio file instead.",
      );
      return;
    }
    const button = byId(`${kind}-record`);
    let mediaStream;
    audioBusy = true;
    updateProfile();
    button.disabled = true;
    say(`${kind}-status`, "Waiting for microphone permission…");
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(mediaStream),
        chunks = [];
      const started = Date.now();
      const state = { media, kind, stream: mediaStream };
      recorder = state;
      updateProfile();
      button.textContent = "Stop recording";
      button.classList.add("recording");
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      state.interval = setInterval(
        () =>
          say(
            `${kind}-status`,
            `Recording locally · ${Math.floor((Date.now() - started) / 1000)} s. ${kind === "sample" ? "Read at least 10 seconds." : "Speak naturally in your selected language."}`,
          ),
        250,
      );
      state.timeout = setTimeout(
        () => {
          if (media.state === "recording") media.stop();
        },
        kind === "sample" ? 29000 : 59000,
      );
      media.onstop = async () => {
        clearInterval(state.interval);
        clearTimeout(state.timeout);
        mediaStream.getTracks().forEach((track) => track.stop());
        recorder = null;
        button.textContent =
          kind === "sample" ? "◉ Record my voice" : "◉ Record a message";
        button.classList.remove("recording");
        await acceptRecording(
          new Blob(chunks, { type: media.mimeType }),
          kind,
          true,
        );
      };
      media.onerror = () => {
        say(
          `${kind}-status`,
          "Recording failed. Check microphone access or upload audio.",
        );
        if (media.state !== "inactive") media.stop();
      };
      media.start();
    } catch {
      mediaStream?.getTracks().forEach((track) => track.stop());
      if (recorder) {
        clearInterval(recorder.interval);
        clearTimeout(recorder.timeout);
      }
      recorder = null;
      audioBusy = false;
      button.textContent =
        kind === "sample" ? "◉ Record my voice" : "◉ Record a message";
      button.classList.remove("recording");
      updateProfile();
      say(
        `${kind}-status`,
        "Microphone access was unavailable. You can allow it in browser settings or upload audio.",
      );
    }
  }
  for (const kind of ["sample", "message"]) {
    byId(`${kind}-record`).onclick = () => record(kind);
    byId(`${kind}-upload`).onchange = async (event) => {
      const file = event.target.files[0];
      if (file) await acceptRecording(file, kind);
      event.target.value = "";
    };
  }
  byId("sample-clear").onclick = () => {
    if (working || audioBusy || recorder) return;
    recordings.sample = null;
    clearAudio(byId("sample-player"));
    byId("sample-clear").hidden = true;
    say(
      "sample-status",
      "Local sample removed. No recording is kept by Pawse.",
    );
    updateProfile();
  };
  byId("clone-voice").onclick = () =>
    task("clone-status", "Creating your voice at Gradium…", async () => {
      requireChecked(
        "own-voice-consent",
        "Confirm this is your own voice and that you consent to cloning it.",
      );
      if (!recordings.sample)
        throw Error("Record or upload 10–30 seconds of your own voice first.");
      resetPreview();
      updateProfile(
        await api("clone", {
          ...consent(),
          own_voice_consent: true,
          audio: recordings.sample,
          sample_language: byId("sample-language").value,
        }),
      );
      say(
        "clone-status",
        profile.german_voice_id
          ? "Your German voice is created. Listen to its preview before generating a script."
          : "Your voice is created. Next, create a German version and listen to the preview.",
      );
    });
  byId("localize-voice").onclick = () =>
    task("clone-status", "Creating your German voice candidate…", async () => {
      resetPreview();
      updateProfile(await api("localizations", consent()));
      for (
        let attempt = 0;
        attempt < 6 && !profile.candidate_ready;
        attempt++
      ) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        updateProfile(await api("localizations/current"));
      }
      say(
        "clone-status",
        profile.candidate_ready
          ? "Your German candidate is ready. Preview it before saving."
          : "Your German candidate is still processing. Use “Check readiness” in a moment.",
      );
    });
  byId("check-voice").onclick = () =>
    task("clone-status", "Checking your German voice…", async () => {
      updateProfile(await api("localizations/current"));
      say(
        "clone-status",
        profile.candidate_ready
          ? "Ready to preview in German."
          : "Still processing. You can check again shortly.",
      );
    });
  byId("preview-voice").onclick = () =>
    task("clone-status", "Generating a short German preview…", async () => {
      resetPreview();
      attachAudio(
        byId("voice-preview"),
        await api("preview", consent(), { audio: true }),
      );
      if (!profile.german_voice_id) byId("listened-label").hidden = false;
      say(
        "clone-status",
        "Press play and listen to the whole preview. Pawse identifies itself as your AI assistant.",
      );
    });
  byId("voice-preview").onended = () => {
    byId("preview-listened").disabled = false;
  };
  byId("preview-listened").onchange = () => updateProfile();
  byId("save-voice").onclick = () =>
    task("clone-status", "Saving your German voice…", async () => {
      requireChecked(
        "preview-listened",
        "Listen to the preview and confirm that you want to use it.",
      );
      updateProfile(
        await api("localizations/current/save", {
          ...consent(),
          listened_to_preview: true,
        }),
      );
      say(
        "clone-status",
        "Your own German voice is ready for reviewed scripts and Mimi’s rehearsal.",
      );
    });
  byId("copy-voice-id").onclick = async () => {
    if (!profile.german_voice_id) return;
    try {
      await navigator.clipboard.writeText(byId("saved-voice-id").textContent);
      say(
        "saved-voice-status",
        "Copied. Save this line in the server’s private .env to reuse your German voice after restarting.",
      );
    } catch {
      say(
        "saved-voice-status",
        "Select and copy the voice configuration line above.",
      );
    }
  };
  byId("delete-voice").onclick = () =>
    task(
      "clone-status",
      "Deleting voices created in this session…",
      async () => {
        await api("profile", null, { method: "DELETE" });
        resetPreview();
        await refreshProfile();
        say(
          "clone-status",
          "Your session’s created voices have been deleted from Gradium. Remove your local sample separately if you wish.",
        );
      },
    );
  byId("voice-language").onchange = () => {
    byId("subtitle-language").value = byId("voice-language").value;
  };
  byId("transcribe-message").onclick = () =>
    task("script-status", "Listening with Gemini…", async () => {
      requireChecked(
        "gemini-voice-consent",
        "Enable sharing with Gemini before transcribing.",
      );
      if (!recordings.message) throw Error("Record or upload a message first.");
      const result = await api("transcriptions", {
        audio: recordings.message,
        language: byId("voice-language").value,
        share_with_gemini: true,
      });
      byId("voice-message").value = result.text;
      say(
        "script-status",
        result.text
          ? "Transcript ready. Check the words before preparing your German script."
          : "No clear speech was detected. Please try again or type your message.",
      );
    });
  byId("handoff-to-voice").onclick = () => {
    byId("voice-message").value = byId("handoff-text").textContent.slice(
      0,
      4000,
    );
    byId("voice-language").value = byId("care-language").value;
    byId("subtitle-language").value = byId("care-language").value;
    byId("voice-recipient").value = "vet";
    say(
      "script-status",
      "Your care notes are copied here. Review them and enable Gemini sharing before preparing your German call.",
    );
    byId("voice").scrollIntoView({ behavior: "smooth" });
  };
  byId("copy-to-care").onclick = () => {
    byId("query").value = byId("voice-message").value;
    byId("care-language").value = byId("voice-language").value;
    say(
      "script-status",
      "Message copied to the care form below. Review the care form’s sharing choices before submitting.",
    );
    byId("care").scrollIntoView({ behavior: "smooth" });
  };
  function renderLines(container, lines) {
    container.replaceChildren();
    lines.forEach((line) => {
      const article = make(
        "div",
        null,
        "script-line" +
          (line.speaker && line.speaker !== "Pawse" ? " recipient" : ""),
      );
      article.append(
        make("span", line.speaker || "Pawse · German draft", "script-speaker"),
      );
      const german = make("p", line.german);
      german.lang = "de";
      article.append(german, make("p", line.subtitle, "subtitle"));
      container.append(article);
    });
  }
  byId("voice-script-form").onsubmit = (event) => {
    event.preventDefault();
    task(
      "script-status",
      "Preparing German words and matching subtitles…",
      async () => {
        requireChecked(
          "gemini-voice-consent",
          "Enable sharing with Gemini before preparing a script.",
        );
        if (!byId("voice-message").value.trim())
          throw Error("Type or transcribe your message first.");
        const result = await api("scripts", {
          message: byId("voice-message").value,
          input_language: byId("voice-language").value,
          subtitle_language: byId("subtitle-language").value,
          recipient: byId("voice-recipient").value,
          target_language: "de",
          share_with_gemini: true,
        });
        scriptLines = result.lines;
        renderLines(byId("script-lines"), scriptLines);
        clearAudio(byId("speech-player"));
        byId("speech-download").hidden = true;
        say(
          "script-status",
          "Draft ready. Review the German script and subtitles. Nothing has been sent to the recipient.",
        );
      },
    );
  };
  async function speak(text, player, download) {
    requireChecked(
      "speech-consent",
      "In the voice studio, enable sharing the reviewed German script with Gradium first.",
    );
    if (!profile.gradium_configured)
      throw Error(
        "Gradium is not configured yet. Add GRADIUM_API_KEY to the server’s .env and restart.",
      );
    if (byId("speech-voice").value === "my_voice" && !profile.my_voice_ready)
      throw Error(
        "Set up your own German voice first, or explicitly select “Standard German voice” in the voice studio.",
      );
    const blob = await api(
      "speech",
      {
        text,
        language: "de",
        voice: byId("speech-voice").value,
        share_with_gradium: true,
      },
      { audio: true },
    );
    if (!player.isConnected)
      throw Error(
        "Audio is ready, but you changed the scene. Return to that scene and generate it again.",
      );
    attachAudio(player, blob, download);
  }
  byId("speak-script").onclick = () =>
    task("speech-status", "Generating your German audio…", async () => {
      await speak(
        scriptLines.map((line) => line.german).join(" "),
        byId("speech-player"),
        byId("speech-download"),
      );
      say(
        "speech-status",
        "Audio ready to play or download. No call has been placed.",
      );
    });
  byId("copy-script").onclick = async () => {
    try {
      await navigator.clipboard.writeText(
        scriptLines
          .map((line) => `${line.german}\n${line.subtitle}`)
          .join("\n\n"),
      );
      say("speech-status", "German script and subtitles copied.");
    } catch {
      say(
        "speech-status",
        "Clipboard unavailable. Select and copy the script above.",
      );
    }
  };
  function allowedStep(index) {
    return (
      index <= 2 ||
      (index === 3 && reviewedSlot) ||
      (index === 4 && reviewedSlot && Boolean(choice)) ||
      (index === 5 && confirmed)
    );
  }
  function demoButton(text, onClick, className = "secondary") {
    const button = make("button", text, className);
    button.type = "button";
    button.onclick = onClick;
    return button;
  }
  function sceneAside() {
    const aside = make("aside", null, "scene-aside");
    aside.append(make("span", "SIMULATED CASE", "badge simulation"));
    const titles = [
      "Mimi’s case",
      "One useful follow-up",
      "Calendar · simulated",
      "The numbers, explained",
      "Owner approval",
      "Keep it all together",
    ];
    aside.append(make("h3", titles[scene]));
    const notes = [
      [
        "Zurich, Switzerland",
        "Concern: limping",
        "Input: a photo, audio or text",
        "Live video analysis is not connected.",
      ],
      [
        "What happened? A jump from a wardrobe.",
        "Request: a vet assessment today.",
        "This story is not an assessment of your cat.",
      ],
      [
        "Free from 16:00 in the demo calendar.",
        "Proposed clinic visit: 16:30.",
        "Home visit: evening time still unknown.",
      ],
      [
        `CHF ${demo.costs.treatment} treatment − CHF ${demo.costs.reimbursed} reimbursement = CHF ${demo.costs.treatment - demo.costs.reimbursed} owner’s share.`,
        `Clinic: + CHF ${demo.costs.taxi} taxi. Home: + CHF ${demo.costs.home_visit_extra} excluded surcharge.`,
        ...demo.costs.exclusions,
      ],
      [
        choice === "clinic"
          ? "Request 16:30 at the practice."
          : "Request a confirmed evening visit time.",
        "Request an itemised invoice.",
        "Ask the owner before physiotherapy.",
        "This button rehearses approval; it does not book.",
      ],
      demo.checklist,
    ];
    const list = make("ul");
    notes[scene].forEach((note) => list.append(make("li", note)));
    aside.append(list);
    return aside;
  }
  function renderDemo() {
    if (!demo) return;
    const previousAudio = byId("demo-audio-player");
    if (previousAudio) clearAudio(previousAudio);
    const step = demo.steps[scene],
      root = byId("demo-scene");
    const steps = byId("demo-steps");
    steps.replaceChildren();
    const labels = [
      "Notice",
      "Understand",
      "Vet",
      "Insurance",
      "Confirm",
      "Together",
    ];
    demo.steps.forEach((item, index) => {
      const button = demoButton(
        `${String(index + 1).padStart(2, "0")} ${labels[index]}`,
        () => {
          scene = index;
          renderDemo();
        },
        "story-step",
      );
      button.append(make("span", item.time));
      button.disabled = !allowedStep(index);
      if (index === scene) button.setAttribute("aria-current", "step");
      steps.append(button);
    });
    root.replaceChildren(
      make("span", `${step.time} · simulated scenario`, "badge simulation"),
      make("h3", step.title, "scene-heading"),
      make("p", step.description, "scene-description"),
    );
    const content = make("div", null, "scene-content"),
      main = make("div");
    let lines = scene === 4 && choice === "home" ? step.home_lines : step.lines;
    if (scene === 5 && choice === "home") lines = [];
    if (scene < 2) {
      const illustration = make("div", null, "scene-illustration");
      illustration.append(
        make("span", scene === 0 ? "🐈" : "♡", "mimi"),
        make(
          "p",
          scene === 0
            ? "“My cat is limping. Please help me.”"
            : "“She jumped off the wardrobe.”",
        ),
        make(
          "span",
          scene === 0
            ? "Your language. A calm place to start."
            : "Pawse prepares the details a vet needs.",
          "small",
        ),
      );
      main.append(illustration);
    }
    if (scene === 3) {
      const costs = make("div", null, "story-costs");
      for (const option of ["clinic", "home"]) {
        const button = demoButton(
          option === "clinic" ? "A · Visit the clinic" : "B · Vet at home",
          () => {
            choice = option;
            confirmed = false;
            renderDemo();
          },
          "cost-option",
        );
        button.setAttribute("aria-pressed", String(choice === option));
        button.append(
          make("strong", `CHF ${demo.costs[option]}`),
          make(
            "span",
            option === "clinic"
              ? "Estimated out of pocket · taxi included"
              : "Estimated out of pocket · home surcharge included",
          ),
        );
        costs.append(button);
      }
      main.append(costs, make("p", demo.costs.assumptions, "small"));
    }
    if (lines.length) {
      const transcripts = make("div", null, "script-lines");
      renderLines(transcripts, lines);
      main.append(transcripts);
    }
    if (scene === 2) {
      const review = demoButton(
        reviewedSlot
          ? "✓ 16:30 reviewed for this demo"
          : "16:30 works for me in this demo",
        () => {
          reviewedSlot = true;
          renderDemo();
        },
      );
      review.style.marginTop = "16px";
      main.append(review);
    }
    if (scene === 4) {
      const approve = demoButton(
        confirmed
          ? "✓ Demo request approved"
          : choice === "clinic"
            ? "Approve the demo clinic request"
            : "Approve the demo home-visit request",
        () => {
          confirmed = true;
          renderDemo();
        },
      );
      approve.style.marginTop = "16px";
      main.append(approve);
    }
    if (scene === 5) {
      const summary = make("div", null, "scene-aside");
      summary.style.marginTop = "18px";
      summary.append(
        make(
          "h3",
          choice === "clinic"
            ? "Your rehearsal plan"
            : "Your home-visit rehearsal plan",
        ),
        make(
          "p",
          choice === "clinic"
            ? "16:05 taxi → 16:30 vet · estimated CHF 385 out of pocket."
            : "Evening home visit · time still to be confirmed · estimated CHF 510 out of pocket.",
        ),
        make(
          "p",
          "All calls, appointments, transport and coverage in this story are simulated. Confirm them directly for a real case.",
          "small",
        ),
      );
      main.append(summary);
    }
    if (lines.some((line) => line.speaker === "Pawse")) {
      const area = make("div", null, "demo-audio");
      const status = make(
        "p",
        "Hear only Pawse’s words; recipient replies remain a simulated transcript.",
        "small",
      );
      status.id = "demo-audio-status";
      status.setAttribute("role", "status");
      const player = make("audio");
      player.id = "demo-audio-player";
      player.controls = true;
      player.hidden = true;
      const download = make("a", "Download rehearsal audio ↓", "text-button");
      download.download = "pawse-mimi-rehearsal.wav";
      download.hidden = true;
      const button = demoButton("♫ Hear Pawse’s German script", () =>
        task("demo-audio-status", "Generating rehearsal audio…", async () => {
          await speak(
            lines
              .filter((line) => line.speaker === "Pawse")
              .map((line) => line.german)
              .join(" "),
            player,
            download,
          );
          if (status.isConnected)
            status.textContent = "Audio ready. No phone call has been placed.";
        }),
      );
      button.style.marginTop = "16px";
      area.append(button, status, player, download);
      main.append(area);
    }
    content.append(main, sceneAside());
    root.append(content);
    byId("demo-back").disabled = scene === 0;
    byId("demo-next").disabled = scene === 5 || !allowedStep(scene + 1);
    byId("demo-next").textContent =
      scene === 5 ? "Rehearsal complete ✓" : "Continue →";
    say(
      "demo-position",
      `${scene + 1} of ${demo.steps.length} · no real calls`,
    );
  }
  byId("demo-back").onclick = () => {
    if (scene > 0) {
      scene--;
      renderDemo();
    }
  };
  byId("demo-next").onclick = () => {
    if (scene < 5 && allowedStep(scene + 1)) {
      scene++;
      renderDemo();
    }
  };
  refreshProfile().catch(() => {
    say(
      "voice-service-status",
      "Voice service status could not be loaded. Record locally or retry after the server is ready.",
    );
  });
  fetch("/api/v1/demo/mimi")
    .then((response) => {
      if (!response.ok) throw Error();
      return response.json();
    })
    .then((data) => {
      demo = data;
      say("demo-notice", data.notice);
      renderDemo();
    })
    .catch(() => {
      say(
        "demo-notice",
        "Mimi’s rehearsal is unavailable. Try reloading after the server is ready.",
      );
      byId("demo-back").disabled = true;
      byId("demo-next").disabled = true;
    });
  window.addEventListener("beforeunload", () => {
    if (recorder) {
      recorder.stream.getTracks().forEach((track) => track.stop());
      clearTimeout(recorder.timeout);
      clearInterval(recorder.interval);
    }
    for (const url of urls.values()) URL.revokeObjectURL(url);
  });
  updateProfile();
})();
