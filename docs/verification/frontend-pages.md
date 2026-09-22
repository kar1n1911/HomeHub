# Three-page frontend verification

2026-09-22, frontend 0.2.2.

- Overview (`/#overview`, also the default `/`) shows household metrics, up to
  three pending tasks, and three device previews with links to their pages.
- Tasks (`/#tasks`) owns task creation, filtering and completion.
- Devices (`/#devices`) owns device registration and signal delivery history.
- Navigation uses hash routes rather than scrolling to sections. Existing links
  remain compatible, browser history works, and reload retains the selected page.
- The active link uses `aria-current="page"`; the document title and focused
  heading update on page changes. Unknown hashes fall back to Overview.
- Shared task/device state updates Overview without requiring a reload. Signal
  polling only runs while the Devices component is mounted and cleans up on exit.

Validation: production build and Kubernetes manifest rendering passed. Browser
checks covered all three views, Devices reload, back/forward navigation and
matching active links. Created and completed `Verify dedicated Tasks page` in
Compose, reloaded Tasks and observed the saved checked state. Opened the device
registration form on Devices. Inspected 390px mobile Overview and Devices layouts.
The viewport override was reset after inspection.

The video plan now instructs the presenter to navigate to Tasks and Devices
before the corresponding live workflows. Earlier Lighthouse measurements in
frontend-lighthouse.json apply to release 0.2.1, not this routing change.
