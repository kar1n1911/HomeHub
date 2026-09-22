# Frontend refresh verification

Date: 2026-09-22. Frontend image: `kar1n1911/homehub-frontend:0.2.1`.
Backend images remain on `0.2.0`. Published frontend supports Linux AMD64 and ARM64.

## Design and scope

HomeHub is a household operations interface. The requested design-taste-frontend
skill was applied contextually: preserve the existing green identity, logo,
navigation anchors, field order, REST integrations and real data. Its marketing
photography, hero animation, logo-wall and sales-copy rules do not apply here.
Design parameters: variation 5, motion 3, density 4. Native CSS and existing
Phosphor icons; self-hosted Manrope variable font; no new component framework.

The previous layout squeezed device readings and JSON logs into one narrow
column, used inconsistent section themes, and hid navigation on mobile.
The refresh separates tasks, devices and delivery history, adds task filters,
keeps mobile navigation visible, and defaults to three expandable signal records.
A single semantic token system supports System, Light and Dark appearances.
The selected appearance persists locally; data continues to persist in the API.

## Checks performed

- Production build, Python syntax and both Kubernetes manifest renders passed.
- Browser inspection at 1280px desktop and 390px mobile, in light and dark modes.
- 320px device form has no horizontal overflow; keyboard navigation remains usable.
- Created a task, completed it, reloaded and confirmed it remained complete in
  Compose and in the deployed Kubernetes interface. The latter retains
  Review refreshed HomeHub interface as a completed verification task.
- Added Desk temperature (Study, 22.1 C, 3600-second sampling) through the form
  in Compose; reloaded and confirmed the device persisted.
- Completed-only filter includes checked tasks; All restores the complete list.
- Recent signals expand from three to ten and collapse back to three.
- Light preference persists after reload; System responds to emulated dark mode.
- Mocked a failed task POST: an error is shown and the typed draft remains intact.
- Mocked empty task/device responses: useful empty states are displayed.
- Loading skeletons remain present; signal polling and event listeners clean up.
- Reduced motion disables CSS transitions; motion is limited to control feedback.
- Text, buttons, placeholders, input borders and error tokens meet AA contrast:
  muted text 5.08:1 light / 6.92:1 dark; primary button 6.57:1 / 8.66:1;
  input boundaries 3.30:1 / 4.14:1. Keyboard focus has a visible accent outline.
- No authored em dashes, decorative status dots, fake data or marketing imagery.
  Status icons retain accompanying text; disclosure and filtering use native controls.
- Asset responses use gzip and immutable caching for fingerprinted files;
  index.html revalidates so new releases can load fresh asset names.
- Frontend Kubernetes rollout completed with two ready replicas; published image
  platforms and running image identities were checked by verify-release-images.py.

Browser screenshots are local artifacts under output/playwright (gitignored).
The Compose verification task/device were intentionally retained as visible evidence.

## Lighthouse

Lighthouse 13.5.0 against the deployed NodePort at http://localhost:30080/,
mobile simulated throttling: performance 97, accessibility 100, best practices 100,
SEO 100. LCP 2.0 seconds, CLS 0.087, total blocking time 0 milliseconds.
Machine-readable results: [frontend-lighthouse.json](frontend-lighthouse.json).
These are local lab measurements, not field Core Web Vitals or a complete
accessibility certification. INP requires real interaction/field measurement.
