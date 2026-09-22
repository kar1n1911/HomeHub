import "@fontsource-variable/manrope";
import Devices from "./Devices";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle,
  Sun,
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
      {state === "error" ? "Connection issue" : "Connected"}
    </span>
  );
}

const pages = {
  overview: { title: "Overview", description: "People, shared tasks, and the devices that keep home running." },
  tasks: { title: "Tasks", description: "Plan shared work, track progress, and make room for what matters." },
  devices: { title: "Devices", description: "Manage your connected devices and follow every signal." }
};
function currentPage() {
  const name = window.location.hash.slice(1);
  return Object.hasOwn(pages, name) ? name : "overview";
}

function App() {
  const [theme, setTheme] = useState(() => {
    try { const saved = localStorage.getItem("homehub-theme"); return ["light", "dark"].includes(saved) ? saved : "system"; } catch { return "system"; }
  });
  const [activeSection, setActiveSection] = useState(currentPage);
  const [taskFilter, setTaskFilter] = useState("all");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("homehub-theme", theme); } catch { /* Storage may be unavailable. */ }
  }, [theme]);
  useEffect(() => {
    const update = () => setActiveSection(currentPage());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
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
  const pageHeading = useRef(null);
  useEffect(() => {
    document.title = `${pages[activeSection].title} | HomeHub`;
    if (state === "ready") {
      window.scrollTo(0, 0);
      pageHeading.current?.focus({ preventScroll: true });
    }
  }, [activeSection, state]);

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
      setTaskFilter("all");
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

  const visibleTasks = data.tasks.filter(task => taskFilter === "all" || (taskFilter === "completed" ? task.completed : !task.completed));

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
      <a className="skip-link" href={`#${activeSection}`} onClick={(event) => { event.preventDefault(); pageHeading.current?.focus(); }}>Skip to content</a>
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="HomeHub home">
          <span className="brand-mark"><House size={22} weight="fill" /></span>
          HomeHub
        </a>
        <nav aria-label="Main navigation">
          {[["Overview", "overview"], ["Tasks", "tasks"], ["Devices", "devices"]].map(([label, id]) => (
            <a key={id} className={activeSection === id ? "active" : ""} href={`#${id}`} aria-current={activeSection === id ? "page" : undefined}>{label}</a>
          ))}
        </nav>
        <div className="header-controls">
          <Status state={state} />
          <div className="theme-control"><Sun size={18} aria-hidden="true" />
            <select aria-label="Appearance" value={theme} onChange={event => setTheme(event.target.value)}>
              <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
            </select>
          </div>
        </div>
      </header>

      <main id="main-content" tabIndex={-1}>
        <section className="intro">
          <div>
            <p className="eyebrow">{activeSection === "overview" ? "Household overview" : data.household?.name || "Your home"}</p>
            <h1 ref={pageHeading} tabIndex={-1}>{activeSection === "overview" ? data.household?.name || "Your home" : pages[activeSection].title}</h1>
            <p className="lede">{pages[activeSection].description}</p>
          </div>
          {activeSection === "tasks" && <button className="primary-button" type="button" ref={addTaskButton}
            aria-expanded={showTaskForm} aria-controls="new-task-form"
            disabled={state !== "ready" || creating}
            onClick={() => setShowTaskForm(true)}>
            <Plus size={18} weight="bold" /> Add task
          </button>}
        </section>

        {activeSection === "tasks" && showTaskForm && (
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
        <p className="save-notice" role="status" aria-live="polite">{activeSection === "tasks" ? notice : ""}</p>

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

        {activeSection === "overview" && <>
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

        <div className="overview-grid">
          <section className="panel overview-panel">
            <div className="panel-heading"><div><h2>Up next</h2><p>{data.tasks.length - completedTasks} tasks left to do</p></div><a className="text-button" href="#tasks">View tasks →</a></div>
            <div className="overview-list">{data.tasks.filter(task => !task.completed).slice(0, 3).map(task => <div className="overview-row" key={task.id}><span>{task.title}</span><span className={`priority ${task.priority}`}>{task.priority}</span></div>)}
              {data.tasks.every(task => task.completed) && <p className="device-hint">You’re all caught up. Plan your next task on the Tasks page.</p>}
            </div>
          </section>
          <section className="panel overview-panel">
            <div className="panel-heading"><div><h2>Connected home</h2><p>{onlineDevices} of {data.devices.length} devices online</p></div><a className="text-button" href="#devices">View devices →</a></div>
            <div className="overview-list">{data.devices.slice(0, 3).map(device => <div className="overview-row" key={device.id}><div><strong>{device.name}</strong><small>{device.room}</small></div><span>{device.value}</span></div>)}
              {!data.devices.length && <p className="device-hint">Add your first device on the Devices page.</p>}
            </div>
          </section>
        </div>
        </>}

        {activeSection === "tasks" && <div className="tasks-page">
          <section className="panel tasks-panel">
            <div className="panel-heading">
              <div><h2>Shared tasks</h2><p>Track your household's shared work</p></div>
              <span className="task-count">{data.tasks.length} tasks</span>
            </div>
            <div className="task-toolbar" role="group" aria-label="Filter tasks">
              {[["all", "All", data.tasks.length], ["active", "To do", data.tasks.length - completedTasks], ["completed", "Completed", completedTasks]].map(([key, label, count]) => (
                <button type="button" key={key} aria-pressed={taskFilter === key} onClick={() => setTaskFilter(key)}>{label}<span>{count}</span></button>
              ))}
            </div>
            {visibleTasks.length ? (
              <div className="task-list">
                {visibleTasks.map((task) => (
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
            ) : <div className="empty-state"><CheckCircle size={30} aria-hidden="true" /><h3>{taskFilter === "active" ? "You’re all caught up" : taskFilter === "completed" ? "No completed tasks yet" : "Make room for your first task"}</h3><p>{taskFilter === "completed" ? "Tick a task when it’s done. It will appear here." : "Use Add task to plan what needs doing at home."}</p></div>}
          </section>

        </div>}
        {activeSection === "devices" && <div className="devices-page">
          <Devices devices={data.devices} onAdded={(device) => setData(current => ({ ...current, devices: [...current.devices, device] }))} />
        </div>}
      </main>

      <footer>
        <span>HomeHub household management</span>
        <span>Shared tasks. Connected home.</span>
      </footer>
    </div>
  );
}

export default App;
