# Model access and allocation

The team's project key was tested on 10 October 2026 with small synthetic inputs. The machine-readable [access report](model-access-check.json) records the checks. A listed model is not automatically callable: the report separates the model list from completed requests.

| Model/service | Observed result | Assign to |
| --- | --- | --- |
| `gemini-3-flash-preview` | Text, synthetic PNG and silent WAV returned HTTP 200 with text | Default care understanding, multilingual transcription and German script preparation |
| `gemini-3.1-pro-preview` | Text returned HTTP 200 with text | Optional deeper reasoning experiments on difficult, cited evidence; not required for the default flow |
| `gemini-embedding-001` | `embedContent` returned HTTP 200 with a vector | Next retrieval iteration: embed the reviewed corpus and index with matching query vectors |
| `gemini-2.5-flash` | Text returned HTTP 404 despite appearing in a listing | Do not use as this project's default |
| Gradium clone, localization and TTS | Contract integrated and mocked; key absent | Voice teammate; own voice sample → German candidate → human preview → speech |
| Gemini Live / phone carrier | No live end-to-end verification | Future streaming/telephony integration; not a completed capability |

The tests establish access only. They do not establish clinical reliability, translation accuracy, voice identity similarity, latency under load or availability in another project. The WAV contained silence, and the PNG was synthetic. Real multilingual recordings, cat photos and consenting speaker samples still require evaluation.

## Configuration

`GEMINI_MODEL=gemini-3-flash-preview` is the shared default. `GEMINI_CARE_MODEL` optionally overrides care assessment, and `GEMINI_VOICE_MODEL` optionally overrides transcription/translation. Blank overrides fall back to the shared model. To experiment with Pro for care, set `GEMINI_CARE_MODEL=gemini-3.1-pro-preview`; the existing deadline still applies and partial results remain possible. There is no automatic model escalation or fallback to an unverified model.

The workflow coordinator, clinic filtering/ranking, phone sanitization, cost arithmetic and evidence citation checks are ordinary code. They do not need separate LLMs. “Agent” describes a responsibility and contract, not a requirement to buy a different model for every box in the architecture.

The current knowledge module uses lexical retrieval, not embeddings. Migrating to Gemini embeddings requires building a new index: the legacy OpenAI `text-embedding-3-small` vectors must not be mixed with Gemini vectors. Keep the model name, dimension, corpus hash and version with each index.

## Repeat the access check

From the repository root, after configuring the ignored `.env`:

```sh
.venv/bin/python scripts/probe_models.py
```

This opt-in command makes billable API requests using synthetic data. It stores model names and success/status metadata, never credentials or raw provider error bodies. Ordinary unit tests remain fully mocked and do not spend API credits.
