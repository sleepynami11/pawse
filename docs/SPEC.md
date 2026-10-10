# Pawse — initial product spec

Status: draft for the Tech Europe AI Hackathon. This is a proposed scope, not an implementation report.

## Product goal

Make a small online task accessible through a friendly, voice-driven cat assistant. The first demo should prove a complete path from a spoken request to a tool result and spoken response.

## Primary user story

As a user, I can ask Pawse to perform one supported online task, see whether it is working, and receive an understandable result without navigating a complex interface.

## Proposed demo

Read a public web page and summarize it in three points. This is a candidate first task; the team should confirm it before implementation.

## MVP requirements

| Area | Requirement | Completion evidence |
| --- | --- | --- |
| Voice | Start and stop microphone capture; receive spoken replies | Live interaction with the configured Gemini model |
| Tool use | Dispatch one supported function and return its result | Visible tool result from a real execution |
| Interface | Idle, listening, working, speaking, and error states | State transitions during the demo |
| Transparency | Show transcript and result | User can inspect what was requested and returned |
| Failure handling | Handle denied microphone permission, dropped sessions, and failed tools | Useful error message and recovery action |
| Credentials | Keep permanent keys on the backend | Browser receives only a constrained short-lived token |

## Proposed integration

1. User starts a voice session.
2. Backend issues a short-lived Live API token.
3. Browser establishes a Live connection and streams microphone audio.
4. A function call is routed through the app to its tool dispatcher.
5. Backend validates arguments and performs the supported operation.
6. App returns the actual tool result to Live; Pawse speaks and displays the outcome.

The app must not report success before the tool confirms it. Operations with external side effects should have an explicit user confirmation step. The first MVP can avoid those operations entirely by using a read-only task.

For a public-page retrieval tool, validate URLs and block private/local network destinations, including redirects; bound response size and request time. Treat page content as data, not instructions.

## Not in the initial scope

- Autonomous purchases or account management.
- Unrestricted control of a user's computer.
- Persistent cross-session memory.
- Custom-trained voice or voice cloning.
- Multiple agents or a general workflow builder.

## Decisions still open

- Frontend and backend stack.
- Exact Live model available to the hackathon project.
- First task and tool schema.
- Cat artwork and animation assets, including their licensing.
- Deployment target and post-event hosting.

## Demo acceptance checklist

- [ ] A teammate can reproduce setup using the README.
- [ ] A real spoken request leads to a real tool execution.
- [ ] The spoken answer matches the returned result.
- [ ] Failure is shown honestly when the tool fails.
- [ ] No permanent key is shipped to the browser or committed.
- [ ] Demo materials distinguish working features from future plans.
