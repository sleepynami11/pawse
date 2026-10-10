const $ = (id) => document.getElementById(id);
let photo = null,
  requestId = null,
  busy = false;
const names = {
  assessment: "Preparing care guidance",
  clinics: "Finding nearby veterinary care",
};
function node(tag, text, className) {
  const e = document.createElement(tag);
  if (text) e.textContent = text;
  if (className) e.className = className;
  return e;
}
function action(label, url) {
  const a = node("a", label, "button secondary");
  a.href = url;
  a.target = url.startsWith("tel:") ? "_self" : "_blank";
  a.rel = "noopener noreferrer";
  return a;
}
function assessmentCard(a) {
  const box = $("assessment");
  box.className = "panel";
  box.replaceChildren(
    node(
      "span",
      a.urgency.replaceAll("_", " "),
      "badge " + (a.urgency === "emergency" ? "emergency" : ""),
    ),
    node("h3", "Your next step"),
    node("p", a.summary),
    node("p", a.disclaimer, "small"),
  );
  if (a.questions?.length) {
    box.append(node("h3", "Useful details for the vet"));
    a.questions.forEach((q) => box.append(node("p", "• " + q, "small")));
  }
  if (a.services_to_ask_about?.length)
    box.append(
      node(
        "p",
        "Ask the clinic about: " + a.services_to_ask_about.join(", "),
        "small",
      ),
    );
}
function clinicCards(clinics) {
  const root = $("clinics");
  root.replaceChildren(node("h3", "Nearby veterinary care"));
  if (!clinics.length) {
    root.append(
      node(
        "p",
        "No verified clinic results returned. Use the map search below or your usual vet’s contact number.",
        "warning",
      ),
    );
    return;
  }
  clinics.forEach((c) => {
    const box = node("article", null, "panel clinic-card");
    if (c.distance_km !== null)
      box.append(node("span", c.distance_km + " km", "distance"));
    box.append(node("h3", c.name), node("p", c.address));
    const list = node("ul");
    c.reasons.forEach((r) => list.append(node("li", r)));
    box.append(list);
    const links = node("div", null, "input-actions");
    if (c.call_url) links.append(action("Call clinic ↗", c.call_url));
    if (c.maps_url) links.append(action("Map & directions ↗", c.maps_url));
    if (c.website) links.append(action("Website ↗", c.website));
    box.append(
      links,
      node("p", c.availability_note, "small"),
      node(
        "p",
        "Source: " +
          c.source.replaceAll("_", " ") +
          " · Retrieved " +
          new Date(c.retrieved_at).toLocaleTimeString(),
        "small",
      ),
    );
    root.append(box);
  });
}
function insuranceCard(i) {
  const root = $("insurance-result");
  root.replaceChildren();
  if (!i) return;
  const card = node("div", null, "panel");
  card.append(
    node("span", "Your policy contact", "badge"),
    node("h3", i.company),
    node("p", "Contact supplied by you · coverage unconfirmed", "small"),
    action("Call insurer ↗", i.call_url),
  );
  i.questions.forEach((q) => card.append(node("p", "• " + q, "small")));
  card.append(node("p", i.note, "small"));
  root.append(card);
}
function handleEvent(e) {
  if (e.type === "safety" || e.type === "assessment")
    assessmentCard(e.assessment);
  if (e.type === "insurance") insuranceCard(e.insurance);
  if (e.type === "clinics") clinicCards(e.clinics);
  if (e.type === "progress")
    $("progress").textContent = (names[e.agent] || e.agent) + " · " + e.status;
  if (e.type === "result") {
    requestId = e.request_id;
    assessmentCard(e.assessment);
    clinicCards(e.clinics);
    insuranceCard(e.insurance);
    $("handoff").hidden = false;
    $("handoff-text").textContent = e.handoff;
    $("progress").textContent =
      (e.status === "partial"
        ? "Your available next steps"
        : "Your care plan") +
      " · " +
      (e.elapsed_ms / 1000).toFixed(1) +
      " seconds";
    $("limitations").replaceChildren(
      node("span", e.completeness + " "),
      action("Open veterinary map search ↗", e.search_url),
    );
    if (e.warnings.length) {
      const warning = node(
        "p",
        "Some services were unavailable: " +
          e.warnings.map((w) => w.replaceAll("_", " ")).join("; ") +
          ". Your available actions are shown above.",
        "warning",
      );
      $("limitations").prepend(warning);
    }
  }
}
async function stream(url, payload, onEvent) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    let error;
    try {
      error = await r.json();
    } catch {}
    throw Error(
      typeof error?.detail === "string"
        ? error.detail
        : error?.error?.fields?.map((x) => x.message).join("; ") ||
            "Request failed. Please check your inputs and try again.",
    );
  }
  const reader = r.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let index;
      while ((index = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        const data = chunk
          .split("\n")
          .filter((x) => x.startsWith("data:"))
          .map((x) => x.slice(5).trim())
          .join("\n");
        if (data) onEvent(JSON.parse(data));
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}
$("photo").onchange = async () => {
  const file = $("photo").files[0];
  if (!file) return;
  if (
    file.size > 3000000 ||
    !["image/jpeg", "image/png", "image/webp"].includes(file.type)
  ) {
    photo = null;
    $("photo").value = "";
    $("photo-preview").hidden = true;
    $("remove-photo").hidden = true;
    $("photo-status").textContent =
      "Please choose a JPEG, PNG or WebP up to 3 MB.";
    return;
  }
  const data = await new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
  photo = { mime_type: file.type, data: data.split(",")[1] };
  $("photo-preview").src = data;
  $("photo-preview").hidden = false;
  $("remove-photo").hidden = false;
  $("photo-status").textContent =
    "Photo selected. Shared only when you enable AI assistance.";
};
$("remove-photo").onclick = () => {
  photo = null;
  $("photo").value = "";
  $("photo-preview").removeAttribute("src");
  $("photo-preview").hidden = true;
  $("remove-photo").hidden = true;
  $("photo-status").textContent = "Photo removed.";
};
$("locate").onclick = () => {
  if (!navigator.geolocation) {
    $("location-status").textContent =
      "Location is unavailable; enter coordinates manually.";
    return;
  }
  $("location-status").textContent = "Waiting for location permission…";
  navigator.geolocation.getCurrentPosition(
    (p) => {
      $("lat").value = p.coords.latitude;
      $("lng").value = p.coords.longitude;
      $("location-status").textContent =
        "Current coordinates ready. Enable location sharing to search.";
    },
    () => {
      $("location-status").textContent =
        "Could not get location. You can use or edit the Zurich coordinates.";
    },
    { timeout: 10000 },
  );
};
$("care-form").onsubmit = async (e) => {
  e.preventDefault();
  if (busy) return;
  requestId = null;
  busy = true;
  $("submit").disabled = true;
  $("handoff").hidden = true;
  $("clinics").replaceChildren();
  $("limitations").replaceChildren();
  $("progress").textContent = "Preparing your next steps…";
  const insurer = $("insurer").value.trim(),
    phone = $("insurance-phone").value.trim();
  try {
    if (Boolean(insurer) !== Boolean(phone))
      throw Error(
        "Enter both the insurer and its international phone number, or leave both blank.",
      );
    await stream(
      "/api/v1/care/requests?stream=true",
      {
        query: $("query").value,
        cat_name: $("cat-name").value,
        location: { lat: Number($("lat").value), lng: Number($("lng").value) },
        radius_km: Number($("radius").value),
        language: "en",
        red_flags: [
          ...document.querySelectorAll("#red-flags input:checked"),
        ].map((i) => i.value),
        photo,
        insurance: insurer ? { company: insurer, phone } : null,
        share_with_ai: $("ai-consent").checked,
        share_location: $("location-consent").checked,
      },
      handleEvent,
    );
  } catch (err) {
    $("progress").textContent = err.message;
  } finally {
    busy = false;
    $("submit").disabled = false;
  }
};
$("copy").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("handoff-text").textContent);
    $("copy").textContent = "Copied";
  } catch {
    $("copy").textContent = "Select and copy the notes below";
  }
};
$("read-aloud").onclick = () => {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  speechSynthesis.speak(
    new SpeechSynthesisUtterance($("handoff-text").textContent),
  );
};
$("delete").onclick = async () => {
  if (requestId) {
    const r = await fetch(
      "/api/v1/care/requests/" + encodeURIComponent(requestId),
      { method: "DELETE" },
    );
    if (!r.ok && r.status !== 404) {
      $("progress").textContent = "Could not delete result; try again.";
      return;
    }
  }
  requestId = null;
  $("handoff").hidden = true;
  $("handoff-text").textContent = "";
  $("assessment").replaceChildren(node("p", "Result cleared."));
  $("clinics").replaceChildren();
  $("insurance-result").replaceChildren();
  $("limitations").replaceChildren();
  $("remove-photo").click();
  $("progress").textContent = "Result cleared.";
};
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition) {
  $("dictate").onclick = () => {
    if (
      !confirm(
        "Your browser may send audio to its speech recognition provider. Continue?",
      )
    )
      return;
    const r = new Recognition();
    r.lang = "en-GB";
    r.onresult = (e) => {
      $("query").value += " " + e.results[0][0].transcript;
    };
    r.onerror = () => {
      $("progress").textContent =
        "Dictation unavailable. Please type your concern.";
    };
    r.start();
  };
} else {
  $("dictate").disabled = true;
  $("dictate").title =
    "Browser dictation is not available. Gemini Live is not connected yet.";
}
$("agent-form").onsubmit = async (e) => {
  e.preventDefault();
  $("legacy-submit").disabled = true;
  $("legacy-result").textContent = "";
  const task = $("legacy-task").value;
  try {
    await stream(
      "/api/v1/agent/requests",
      {
        mode: task === "chat" ? "chat" : "analysis",
        cat_id: Number($("legacy-cat").value),
        message: $("legacy-message").value,
        analysis_type: task === "chat" ? null : task,
        time_range: "24h",
      },
      (event) => {
        $("legacy-result").textContent += JSON.stringify(event, null, 2) + "\n";
      },
    );
  } catch (err) {
    $("legacy-result").textContent = err.message;
  } finally {
    $("legacy-submit").disabled = false;
  }
};
fetch("/api/v1/capabilities")
  .then((r) => r.json())
  .then((c) => {
    c.new_features.forEach((f) =>
      $("capabilities").append(
        node(
          "span",
          f.id.replaceAll("_", " ") + " · " + f.status.replaceAll("_", " "),
          "capability",
        ),
      ),
    );
    c.analysis_types.forEach((t) => {
      const o = node("option", t.replaceAll("_", " "));
      o.value = t;
      $("legacy-task").append(o);
    });
    c.legacy_intents.forEach((i) =>
      $("catalog").append(
        node(
          "span",
          i.description + " · legacy service required",
          "capability",
        ),
      ),
    );
    c.legacy_tools.forEach((i) =>
      $("catalog").append(
        node(
          "span",
          i.id.replaceAll("_", " ") + " · legacy service required",
          "capability",
        ),
      ),
    );
    $("legacy-status").textContent =
      c.legacy_bridge.replaceAll("_", " ") + ". " + c.note;
    $("legacy-submit").disabled = c.legacy_bridge === "needs_configuration";
  })
  .catch(() => {
    $("legacy-status").textContent = "Could not load service availability.";
  });
