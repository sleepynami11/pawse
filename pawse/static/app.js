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
    if (c.source === "google_places") {
      const attribution = node("p", null, "small maps-attribution");
      attribution.append(
        action("Google Maps", c.maps_url || "https://maps.google.com"),
      );
      box.append(attribution);
    }
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
  $("agent-run-trace").hidden = true;
  $("agent-trace-list").replaceChildren();
  $("progress").textContent = "Preparing your next steps…";
  const insurer = $("insurer").value.trim(),
    phone = $("insurance-phone").value.trim();
  try {
    if (Boolean(insurer) !== Boolean(phone))
      throw Error(
        "Enter both the insurer and its international phone number, or leave both blank.",
      );
    const payload = {
      query: $("query").value,
      cat_name: $("cat-name").value,
      location: { lat: Number($("lat").value), lng: Number($("lng").value) },
      radius_km: Number($("radius").value),
      language: $("care-language").value,
      red_flags: [...document.querySelectorAll("#red-flags input:checked")].map(
        (i) => i.value,
      ),
      photo,
      insurance: insurer ? { company: insurer, phone } : null,
      share_with_ai: $("ai-consent").checked,
      share_location: $("location-consent").checked,
    };
    if ($("agent-workflow").checked) {
      $("progress").textContent =
        "Coordinating care guidance and clinic retrieval. The agent results will appear when the workflow finishes…";
      const response = await fetch("/api/v1/agents/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ care: payload }),
        signal: AbortSignal.timeout(60000),
      });
      const result = await response.json();
      if (!response.ok)
        throw Error(
          typeof result.detail === "string"
            ? result.detail
            : result.error?.fields?.map((field) => field.message).join("; ") ||
                "The agent workflow could not finish. Check your inputs and try again.",
        );
      handleEvent({ ...result.care, type: "result" });
      renderAgentTrace(result);
    } else {
      await stream("/api/v1/care/requests?stream=true", payload, handleEvent);
    }
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
  const utterance = new SpeechSynthesisUtterance($("handoff-text").textContent);
  utterance.lang = { en: "en-GB", zh: "zh-CN", de: "de-CH", hi: "hi-IN" }[
    $("care-language").value
  ];
  speechSynthesis.speak(utterance);
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
  $("agent-run-trace").hidden = true;
  $("agent-trace-list").replaceChildren();
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
    r.lang = { en: "en-GB", zh: "zh-CN", de: "de-CH", hi: "hi-IN" }[
      $("care-language").value
    ];
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
    "Browser dictation is unavailable. Use the multilingual recording studio above.";
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

const agentNames = {};
function renderAgentTrace(result) {
  const list = $("agent-trace-list");
  list.replaceChildren();
  result.trace.forEach((entry) => {
    const row = node("details", null, "trace-item");
    const title = node("summary");
    title.append(
      node(
        "span",
        agentNames[entry.agent_id] || entry.agent_id.replaceAll("_", " "),
      ),
      node(
        "span",
        entry.state.replaceAll("_", " "),
        "badge trace-state " +
          (entry.state === "complete" ? "trace-complete" : ""),
      ),
    );
    row.append(title, node("p", entry.detail, "small"));
    list.append(row);
  });
  const gates = node("details", null, "trace-item");
  gates.append(node("summary", "What still needs review or a connection?"));
  result.actions.forEach((gate) =>
    gates.append(
      node(
        "p",
        `${gate.id.replaceAll("_", " ")}: ${gate.state.replaceAll("_", " ")}. ${gate.required.join("; ")}.`,
        "small",
      ),
    ),
  );
  list.append(gates);
  $("agent-run-note").textContent = result.note;
  $("agent-run-trace").hidden = false;
}
fetch("/api/v1/agents/graph")
  .then((response) => {
    if (!response.ok) throw Error();
    return response.json();
  })
  .then((graph) => {
    graph.agents.forEach((agent, index) => {
      agentNames[agent.id] = agent.name;
      const card = node("article", null, "agent-role");
      card.append(
        node(
          "span",
          `${String(index + 1).padStart(2, "0")} / ${agent.implementation.replaceAll("_", " ")}`,
          "eyebrow",
        ),
        node("h3", agent.name),
        node("p", agent.responsibility),
      );
      card.append(
        node("span", agent.availability.replaceAll("_", " "), "badge"),
      );
      if (agent.model) card.append(node("p", agent.model, "small model-name"));
      card.append(
        node("p", `Team owner: ${agent.owner.replaceAll("_", " ")}`, "small"),
      );
      $("agent-graph").append(card);
    });
    $("agent-graph-note").textContent = graph.note;
  })
  .catch(() => {
    $("agent-graph-note").textContent =
      "Agent responsibilities are unavailable. Reload after the server is ready.";
  });

const chf = (n) => "CHF " + Number(n).toLocaleString("de-CH");
const label = (k) => k.replaceAll("_", " ");
function policyList(entries) {
  const dl = node("dl", null, "policy-facts");
  entries.forEach(([k, v]) => dl.append(node("dt", k), node("dd", String(v))));
  return dl;
}
function coverageDetail(details) {
  const parts = [];
  if (details.annual_limit_chf) parts.push(chf(details.annual_limit_chf) + " a year");
  if (details.limit_chf_per_day)
    parts.push(chf(details.limit_chf_per_day) + " a day, up to " + details.max_days_per_year + " days");
  if (details.includes) parts.push(details.includes.map(label).join(", "));
  return parts.join(" · ");
}
fetch("/api/v1/knowledge/policy")
  .then((response) => {
    if (!response.ok) throw new Error("policy unavailable");
    return response.json();
  })
  .then((p) => {
    const root = $("policy");
    const cost = p.cost_sharing;
    const summary = node("div", null, "policy-grid");
    const schedule = node("article", null, "policy-card");
    schedule.append(
      node("span", "Policy schedule", "badge"),
      node("h3", p.insurer),
      policyList([
        ["Policy number", p.policy_number],
        ["Term", p.term.start + " to " + p.term.end + " (" + p.term.renewal + ")"],
        ["Illness covered from", p.term.illness_covered_from + " (" + p.term.illness_waiting_period_days + "-day waiting period)"],
        ["Annual deductible", chf(cost.annual_deductible_chf) + ", " + cost.deductible_basis],
        ["Reimbursement", Math.round(cost.reimbursement_rate * 100) + "% after the deductible"],
        ["Terms (AVB)", "Edition " + p.avb_edition + ", modeled on " + p.avb_modeled_on],
      ]),
    );
    const cats = node("article", null, "policy-card");
    cats.append(node("span", "Insured cats", "badge"));
    p.insured_animals.forEach((cat) => {
      cats.append(
        node("h3", cat.name),
        node(
          "p",
          [cat.breed, cat.age_years_at_start + " years at start", label(cat.declared_lifestyle)]
            .concat(cat.known_conditions_at_start.length ? ["known: " + cat.known_conditions_at_start.join(", ")] : [])
            .join(" · "),
          "small",
        ),
      );
    });
    summary.append(schedule, cats);

    const covers = node("div", null, "policy-coverages");
    p.coverages.forEach((c) => {
      const row = node("article", null, "policy-coverage " + (c.selected ? "covered" : "not-covered"));
      row.append(
        node("span", c.selected ? "✓ Covered" : "✗ Not covered", "badge" + (c.selected ? "" : " emergency")),
        node("h3", c.label),
      );
      const detail = coverageDetail(c.details);
      if (detail) row.append(node("p", detail, "small"));
      if (c.details.notes) row.append(node("p", c.details.notes, "small"));
      covers.append(row);
    });

    const claims = node("article", null, "policy-card");
    claims.append(
      node("span", "Making a claim", "badge"),
      node("p", "Submit within " + p.claims_process.submit_within_days + " days via " + p.claims_process.channel + "."),
    );
    const docs = node("ul", null, "small");
    p.claims_process.required_documents.forEach((d) => docs.append(node("li", d)));
    claims.append(docs);

    const terms = node("details", null, "policy-terms");
    terms.append(node("summary", "Read the full terms (" + p.clauses.length + " clauses)"));
    p.clauses.forEach((c) => {
      terms.append(node("h4", c.section + " " + c.title), node("pre", c.text.replaceAll("**", "")));
    });

    root.replaceChildren(
      summary,
      node("h3", "What is covered"),
      covers,
      claims,
      terms,
    );
    $("policy-note").textContent = p.disclaimer;
  })
  .catch(() => {
    $("policy-note").textContent =
      "The demo policy is unavailable. Reload after the server is ready.";
  });
