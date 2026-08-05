# AI Red Team Console — Frontend v2

Modern enterprise frontend for the Autonomous AI Red Teaming Framework.
React · TypeScript · Tailwind CSS · Framer Motion · Rive (mascot seam).

---

## Quick start

```bash
# 1. Install dependencies (requires npm/node)
cd frontend-v2
npm install

# 2. Start the Flask API backend in another terminal first
cd ..
python -m api.app          # runs on http://127.0.0.1:8080

# 3. Start the Vite dev server (proxies /api to Flask automatically)
npm run dev                # opens http://localhost:5173
```

For a production build:
```bash
npm run build              # output goes to dist/
npm run preview            # serve the built dist/ locally
```

---

## Project structure

```
frontend-v2/
├── index.html
├── package.json
├── vite.config.ts          # proxies /api → Flask on :8080 in dev
├── tailwind.config.js      # brand colors, shadow tokens, radius tokens
├── tsconfig.json
├── postcss.config.js
└── src/
    ├── main.tsx            # React entry point
    ├── App.tsx             # routing, polling loop, data flow
    ├── index.css           # Tailwind directives + soft-pulse keyframe
    ├── types.ts            # TypeScript types mirroring Flask API JSON shapes
    ├── lib/
    │   └── api.ts          # typed API client (fetch wrapper, no extra dep)
    ├── components/
    │   ├── Header.tsx          # sticky top nav with logo + status badge
    │   ├── Pipeline.tsx        # animated 5-node pipeline + mascot track
    │   ├── Mascot.tsx          # original cloud-assistant SVG mascot (Framer Motion)
    │   ├── RiveMascot.tsx      # Rive integration seam (used when riveSrc is passed)
    │   ├── CurrentRunCard.tsx  # live run summary with progress bar
    │   ├── RunLauncher.tsx     # configure + start a run
    │   ├── MetricCard.tsx      # single metric card (used ×4 on dashboard)
    │   ├── StatusBadge.tsx     # Running / Completed / Failed badge
    │   ├── RiskBadge.tsx       # Critical / High / Medium / Low / Minimal badge
    │   └── icons.tsx           # custom SVG icon set (pipeline stages, badges, actions)
    └── pages/
        ├── Dashboard.tsx       # main demo screen
        ├── PreviousRuns.tsx    # run history cards
        └── ReportViewer.tsx    # document-viewer style attack history
```

---

## Pages

### Dashboard
- OWASP LLM01 header band
- Configure + start a run (objective, target, generator, iterations, fresh KB)
- **Animated pipeline** — the centrepiece: 5 nodes glow one at a time as the mascot
  slides between them. Polls `GET /api/status` every 1.5 s.
- Current run card — strategy, stage, progress bar, attack preview
- Four metric cards — Attacks Executed, Successful Attacks, Risk Level, Score
- Report download buttons (Technical Report, Executive Mitigation PDF)

### Previous Runs
- Card per run: name, date, risk badge, status badge
- Download Technical Report / Mitigation PDF
- "View History" button → opens Report Viewer for that run

### Report Viewer
- Document-viewer style, expandable rows
- Each attack: strategy, outcome pill (Injected/Partial/Blocked), severity, reward
- Expanded: judge analysis, recommendation, attack prompt, target response

---

## Backend API used

All calls go to the same Flask app that also serves `frontend/index.html`.
In dev, Vite proxies `/api/*` to `http://127.0.0.1:8080`.
In production (`npm run build`), copy `dist/` to `frontend-v2-dist/` and either:
- serve it via Flask (`send_from_directory`) the same way the old `frontend/` is, or
- deploy it to any static host and set `VITE_API_BASE` to the Flask URL.

Endpoints consumed:
```
GET  /api/health
GET  /api/objectives
GET  /api/status
GET  /api/runs
GET  /api/reports
GET  /api/history/<run_id>
GET  /api/mitigation/<run_id>        → PDF download
GET  /api/reports/<run_id>/technical/md   → Markdown download
GET  /api/reports/<run_id>/technical/json → JSON download
POST /api/runs                        → start a run
```

---

## Mascot

The default mascot is a custom animated SVG cloud-assistant (`Mascot.tsx`).
Its silhouette is deliberately different from Salesforce's Astro character:
no ears, no hood, no tail — a single rounded blob shape.

To swap in a real Rive animation:

1. Create a `.riv` file in the [Rive editor](https://rive.app) with:
   - A **state machine** named `MascotStateMachine`
   - A **string input** named `pose`
   - States: `idle`, `thinking`, `typing`, `talking`, `inspecting`, `running`, `celebrating`
2. Export to `src/assets/mascot.riv`
3. In `Pipeline.tsx`, add `riveSrc="/src/assets/mascot.riv"` to `<Mascot>`:
   ```tsx
   <Mascot pose={pose} xPercent={xPercent} size={72} riveSrc="/src/assets/mascot.riv" />
   ```

No other code changes needed — `Mascot.tsx` switches to `RiveMascot.tsx` automatically.

---

## Theme tokens (Tailwind)

| Token | Value |
|---|---|
| `brand-500` | `#0176D3` — Salesforce blue, primary |
| `surface` | `#F7F9FC` — page background |
| `card` | `#FFFFFF` — card background |
| `ink` | `#1B2631` — primary text |
| `muted` | `#5B6B7C` — secondary text |
| `line` | `#E4E9F0` — borders |
| `shadow-card` | subtle 2-layer shadow for cards |
| `shadow-glow` | brand-blue focus ring for active pipeline node |

---

## Design principles applied

- **Whitespace first** — generous padding, single-column scannable layout
- **4 metrics max** on the dashboard — not a wall of numbers
- **One active thing at a time** — pipeline node glows, mascot sits there
- **No terminal windows, no raw JSON, no SQL tables** visible to the user
- **Framer Motion** only where it adds meaning: fade-ins, progress bar, pipeline node pulse
- The pipeline is the story — everything else supports it
