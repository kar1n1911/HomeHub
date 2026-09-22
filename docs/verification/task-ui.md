# Task UI verification

Verified on 2026-09-21 against the current local Compose deployment at http://localhost:8080, using a real Chromium browser through Playwright CLI.

## Implemented flow

- Add task opens a form with a required name, optional due date, and low/medium/high priority.
- Submit calls POST `/api/tasks`, adds the server-returned task to the full list, and displays confirmation only after success.
- Each checkbox calls PATCH `/api/tasks/{id}` with the requested completion value. Pending controls are disabled; successful responses update the task and completed count.
- Browser refresh reloads the task list with GET `/api/tasks`; task state is not stored only in React or browser storage.
- Whitespace-only names are rejected. Save failures keep the draft or previous completion state and show a visible error. Ambiguous network failures instruct the user to refresh and check before creating another task.

## Observed results

1. Created `Prepare groceries for Friday` through the UI with due date `2026-09-25` and priority `high`. It appeared as the fifth task, demonstrating removal of the previous four-row truncation.
2. Marked the task complete through its checkbox. The summary changed from `1/5` to `2/5`.
3. Refreshed the browser and later loaded the page in a fresh document after rebuilding the frontend. The task, date, priority, and checked state persisted.
4. Read PostgreSQL directly: task ID 5 contained the expected title/date/priority and `completed = true`.
5. Browser/REST assertions confirmed exactly one matching task with those persisted values.
6. Set the browser offline and tried to uncheck the completed task. The save error was shown and the previously saved checked state remained.
7. Tried an all-whitespace task name: the form displayed `Enter a task name.`. Tried creating `Unsaved draft check` while offline: its input remained in the form and an error appeared. After restoring connectivity, the API confirmed no such task was created.
8. Inspected full-page screenshots at desktop and 390px mobile width. The form, controls, task list, and error messages were readable without visible horizontal clipping.
9. Production frontend build, Python syntax checks, both Kustomize renders, Compose configuration validation, and diff checks passed.

Local screenshots are in `output/playwright/tasks-persisted.png` and `output/playwright/task-form-mobile.png` (ignored verification artifacts). Browser request errors during steps 6 and 7 were deliberately induced by offline mode.

## Runtime and release scope

The local Compose deployment remains running for review. Its new isolated database volume contains the example task above; the older `homehub_homehub-data` volume was not modified. This UI verification was performed against Compose, not a newly deployed Kubernetes application.

The frontend package and Kubernetes image reference now target `0.1.1`, alongside the API release already prepared as `0.1.1`. New release images have not been pushed in this task. The previous Docker Hub `0.1.0` frontend does not include these controls.
