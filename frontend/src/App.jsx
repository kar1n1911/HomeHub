import Devices from "./Devices";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle,
  Clock,
  House,
  Lightning,
  Plus,
  UsersThree,
  WarningCircle
} from "@phosphor-icons/react";

const api = {
  household: "/api/households",
  tasks: "/api/tasks",
  devices: "/api/devices"
};

const emptyData = { household: null, tasks: [], devices: [] };
const emptyTask = { title: "", due_date: "", priority: "medium" };

async function saveTask(url, method, payload) {
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch {
    throw new Error("Connection lost. Refresh the page to check whether your change was saved before trying again.");
  }
  if (!response.ok) {
    if (response.status === 422) {
      throw new Error("Check the task name, date, and priority, then try again.");
    }
    if (response.status === 404) {
      throw new Error("This task no longer exists. Refresh the page to update your list.");
    }
    throw new Error("We couldn't confirm the save. Refresh the page to check your task before trying again.");
  }
  try {
    return await response.json();
  } catch {
    throw new Error("The save response was interrupted. Refresh the page to check your task before trying again.");
  }
}

function Status({ state }) {
  const Icon = state === "error" ? WarningCircle : CheckCircle;
  return (
    <span className={`system-status ${state}`}>
      <Icon size={17} weight="fill" />
      {state === "error" ? "Service issue" : "All services online"}
    </span>
  );
}

function App() {
  const [data, setData] = useState(emptyData);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [draft, setDraft] = useState(emptyTask);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [taskErrors, setTaskErrors] = useState({});
  const [savingTasks, setSavingTasks] = useState(new Set());
  const [notice, setNotice] = useState("");
  const createInFlight = useRef(false);
  const updatesInFlight = useRef(new Set());
  const addTaskButton = useRef(null);

  function closeTaskForm() {
    setShowTaskForm(false);
    setDraft(emptyTask);
    setCreateError("");
    requestAnimationFrame(() => addTaskButton.current?.focus());
  }

  async function createTask(event) {
    event.preventDefault();
    if (createInFlight.current) return;
    const title = draft.title.trim();
    if (!title) {
      setCreateError("Enter a task name.");
      return;
    }
    createInFlight.current = true;
    setCreating(true);
    setCreateError("");
    setNotice("");
    try {
      const task = await saveTask(api.tasks, "POST", { ...draft, title, due_date: draft.due_date || null });
      setData((current) => ({ ...current, tasks: [...current.tasks, task] }));
      closeTaskForm();
      setNotice(`Created “${task.title}”.`);
    } catch (saveError) {
      setCreateError(saveError.message);
    } finally {
      createInFlight.current = false;
      setCreating(false);
    }
  }

  async function setTaskCompleted(task, completed) {
    if (updatesInFlight.current.has(task.id)) return;
    updatesInFlight.current.add(task.id);
    setSavingTasks(new Set(updatesInFlight.current));
    setTaskErrors((current) => ({ ...current, [task.id]: "" }));
    setNotice("");
    try {
      const updated = await saveTask(`${api.tasks}/${task.id}`, "PATCH", { completed });
      setData((current) => ({
        ...current,
        tasks: current.tasks.map((item) => item.id === updated.id ? updated : item)
      }));
      setNotice(`“${updated.title}” marked ${updated.completed ? "complete" : "incomplete"}.`);
    } catch (saveError) {
      setTaskErrors((current) => ({ ...current, [task.id]: saveError.message }));
    } finally {
      updatesInFlight.current.delete(task.id);
      setSavingTasks(new Set(updatesInFlight.current));
    }
  }

  async function loadDashboard() {
    setState("loading");
    setError("");
    try {
      const [householdResponse, taskResponse, deviceResponse] = await Promise.all([
        fetch(api.household),
        fetch(api.tasks),
        fetch(api.devices)
      ]);
      if (![householdResponse, taskResponse, deviceResponse].every((response) => response.ok)) {
        throw new Error("One or more HomeHub services did not respond.");
      }
      const [household, tasks, devices] = await Promise.all([
        householdResponse.json(),
        taskResponse.json(),
        deviceResponse.json()
      ]);
      setData({ household, tasks, devices });
      setState("ready");
    } catch (loadError) {
      setError(loadError.message);
      setState("error");
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const completedTasks = useMemo(
    () => data.tasks.filter((task) => task.completed).length,
    [data.tasks]
  );
  const onlineDevices = useMemo(
    () => data.devices.filter((device) => device.online).length,
    [data.devices]
  );

  if (state === "loading") {
    return (
      <main className="loading-shell" aria-busy="true" aria-label="Loading HomeHub">
        <div className="skeleton wide" />
        <div className="skeleton-grid">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
        <div className="skeleton tall" />
      </main>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="HomeHub home">
          <span className="brand-mark"><House size={22} weight="fill" /></span>
          HomeHub
        </a>
        <nav aria-label="Main navigation">
          <a className="active" href="#overview">Overview</a>
          <a href="#tasks">Tasks</a>
          <a href="#devices">Devices</a>
        </nav>
        <Status state={state} />
      </header>

      <main id="overview">
        <section className="intro">
          <div>
            <p className="eyebrow">Household overview</p>
            <h1>{data.household?.name || "Your home"}</h1>
            <p className="lede">One calm place for people, shared work, and connected devices.</p>
          </div>
          <button className="primary-button" type="button" ref={addTaskButton}
            aria-expanded={showTaskForm} aria-controls="new-task-form"
            disabled={state !== "ready" || creating}
            onClick={() => setShowTaskForm(true)}>
            <Plus size={18} weight="bold" /> Add task
          </button>
        </section>

        {showTaskForm && (
          <form id="new-task-form" className="task-form panel" aria-labelledby="new-task-heading" onSubmit={createTask} aria-busy={creating}>
            <h2 id="new-task-heading">Create a task</h2>
            <fieldset disabled={creating}>
              <div className="task-form-fields">
                <label className="task-title-field" htmlFor="task-title">Task name
                  <input id="task-title" autoFocus required maxLength={160} value={draft.title}
                    onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                    placeholder="e.g. Pick up groceries" />
                </label>
                <label htmlFor="task-due-date">Due date (optional)
                  <input id="task-due-date" type="date" value={draft.due_date}
                    onChange={(event) => setDraft({ ...draft, due_date: event.target.value })} />
                </label>
                <label htmlFor="task-priority">Priority
                  <select id="task-priority" value={draft.priority}
                    onChange={(event) => setDraft({ ...draft, priority: event.target.value })}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </label>
              </div>
              {createError && <p className="task-error" role="alert">{createError}</p>}
              <div className="task-form-actions">
                <button className="secondary-button" type="button" onClick={closeTaskForm}>Cancel</button>
                <button className="primary-button" type="submit">{creating ? "Saving…" : "Create task"}</button>
              </div>
            </fieldset>
          </form>
        )}
        <p className="save-notice" role="status" aria-live="polite">{notice}</p>

        {state === "error" && (
          <section className="error-panel" role="alert">
            <WarningCircle size={24} weight="fill" />
            <div>
              <strong>HomeHub could not load the dashboard.</strong>
              <p>{error}</p>
            </div>
            <button type="button" onClick={loadDashboard}>Try again</button>
          </section>
        )}

        <section className="metrics" aria-label="Household summary">
          <article>
            <span className="icon-box"><UsersThree size={23} /></span>
            <div><strong>{data.household?.members?.filter((member) => member.at_home).length ?? 0}</strong><span>People at home</span></div>
          </article>
          <article>
            <span className="icon-box"><CheckCircle size={23} /></span>
            <div><strong>{completedTasks}/{data.tasks.length}</strong><span>Tasks completed</span></div>
          </article>
          <article>
            <span className="icon-box"><Lightning size={23} /></span>
            <div><strong>{onlineDevices}/{data.devices.length}</strong><span>Devices online</span></div>
          </article>
        </section>

        <div className="content-grid">
          <section className="panel tasks-panel" id="tasks">
            <div className="panel-heading">
              <div><h2>Shared tasks</h2><p>Track your household's shared work</p></div>
              <span className="task-count">{data.tasks.length} tasks</span>
            </div>
            {data.tasks.length ? (
              <div className="task-list">
                {data.tasks.map((task) => (
                  <article className={`task-row ${task.completed ? "completed" : ""}`} key={task.id} aria-busy={savingTasks.has(task.id)}>
                    <label className="task-toggle">
                      <input type="checkbox" checked={task.completed} disabled={savingTasks.has(task.id)}
                        aria-label={`Completed: ${task.title}`}
                        aria-describedby={taskErrors[task.id] ? `task-error-${task.id}` : undefined}
                        onChange={(event) => setTaskCompleted(task, event.target.checked)} />
                    </label>
                    <div className="task-copy">
                      <strong>{task.title}</strong>
                      <span><Clock size={15} /> {task.due_date || "No due date"}</span>
                      {savingTasks.has(task.id) && <span role="status">Saving…</span>}
                    </div>
                    <span className={`priority ${task.priority}`}>{task.priority}</span>
                    {taskErrors[task.id] && <p id={`task-error-${task.id}`} className="task-error" role="alert">{taskErrors[task.id]}</p>}
                  </article>
                ))}
              </div>
            ) : <p className="empty-state">No shared tasks yet.</p>}
          </section>

          <Devices devices={data.devices} onAdded={(device) => setData(current => ({ ...current, devices: [...current.devices, device] }))} />
        </div>
      </main>

      <footer>
        <span>HomeHub household management</span>
        <span>Independently scalable services</span>
      </footer>
    </div>
  );
}

export default App;
