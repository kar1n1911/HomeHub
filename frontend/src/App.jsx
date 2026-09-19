import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle,
  Clock,
  Cpu,
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
          <button className="primary-button" type="button" disabled title="Task creation is planned for the next iteration">
            <Plus size={18} weight="bold" /> Add task
          </button>
        </section>

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
            <div><strong>{data.household?.members?.length ?? 0}</strong><span>People at home</span></div>
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
              <div><h2>Shared tasks</h2><p>What needs attention this week</p></div>
              <a href="#tasks">View all</a>
            </div>
            {data.tasks.length ? (
              <div className="task-list">
                {data.tasks.slice(0, 4).map((task) => (
                  <article className="task-row" key={task.id}>
                    <span className={`task-check ${task.completed ? "done" : ""}`}>
                      {task.completed && <CheckCircle size={22} weight="fill" />}
                    </span>
                    <div className="task-copy">
                      <strong>{task.title}</strong>
                      <span><Clock size={15} /> {task.due_date || "No due date"}</span>
                    </div>
                    <span className={`priority ${task.priority}`}>{task.priority}</span>
                  </article>
                ))}
              </div>
            ) : <p className="empty-state">No shared tasks yet.</p>}
          </section>

          <section className="panel devices-panel" id="devices">
            <div className="panel-heading">
              <div><h2>Devices</h2><p>Live status around the home</p></div>
              <Cpu size={24} />
            </div>
            {data.devices.length ? data.devices.map((device) => (
              <article className="device-row" key={device.id}>
                <span className={`device-icon ${device.online ? "online" : "offline"}`}><Lightning size={19} weight="fill" /></span>
                <div><strong>{device.name}</strong><span>{device.room}</span></div>
                <span className="device-value">{device.value}</span>
              </article>
            )) : <p className="empty-state">No devices connected.</p>}
          </section>
        </div>
      </main>

      <footer>
        <span>HomeHub household management</span>
        <span>Three independently scalable services</span>
      </footer>
    </div>
  );
}

export default App;

