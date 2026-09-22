import { useEffect, useRef, useState } from 'react';
import { Plus, X, ThermometerSimple, Lightbulb, Plug, WifiHigh, WifiSlash, CheckCircle, Clock, CaretDown, PaperPlaneTilt } from '@phosphor-icons/react';

const initial = { name: '', room: '', value: 'Ready', poll_interval_seconds: 60 };
function DeviceIcon({ name }) {
  const Icon = /temperature|climate|sensor/i.test(name) ? ThermometerSimple : /light/i.test(name) ? Lightbulb : Plug;
  return <Icon size={22} aria-hidden="true" />;
}
export default function Devices({ devices, onAdded }) {
  const [draft, setDraft] = useState(initial);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState('');
  const [showAll, setShowAll] = useState(false);
  const saving = useRef(false);
  const addButton = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function refresh() {
      try {
        const response = await fetch('/api/signals/stats', { signal: controller.signal });
        if (!response.ok) throw new Error();
        setStats(await response.json());
        setStatsError('');
      } catch {
        if (!controller.signal.aborted) setStatsError('Delivery status unavailable. Retrying…');
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 5000);
      }
    }
    refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);
  function close() {
    setOpen(false);
    requestAnimationFrame(() => addButton.current?.focus());
  }
  async function add(event) {
    event.preventDefault();
    if (saving.current) return;
    if (!draft.name.trim() || !draft.room.trim()) { setError('Enter a device name and room.'); return; }
    saving.current = true; setBusy(true); setError(''); setNotice('');
    try {
      const response = await fetch('/api/devices', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...draft, poll_interval_seconds: Number(draft.poll_interval_seconds) }) });
      if (!response.ok) throw new Error(response.status === 503 ? 'Signal storage is busy. Please try again later.' : 'Could not add device. Check the fields and try again.');
      const device = await response.json();
      onAdded(device); setDraft(initial); close(); setNotice(`${device.name} added. Its first signal is queued for delivery.`);
    } catch (err) { setError(err instanceof TypeError ? 'Connection lost. Refresh to check whether the device was added before retrying.' : err.message); }
    finally { saving.current = false; setBusy(false); }
  }
  function field(event) { setDraft(current => ({ ...current, [event.target.name]: event.target.value })); }
  return <>
    <section className="panel devices-panel" id="devices">
      <div className="panel-heading">
        <div><h2>Devices</h2><p>Your home, room by room</p></div>
        <button className="secondary-button" ref={addButton} aria-expanded={open} aria-controls="new-device-form" onClick={() => { if (open) close(); else setOpen(true); setError(''); }} disabled={busy}>
          {open ? <X size={16} aria-hidden="true" /> : <Plus size={16} aria-hidden="true" />}{open ? 'Cancel' : 'Add device'}
        </button>
      </div>
      {notice && <p className="task-notice" role="status">{notice}</p>}
      {open && <form id="new-device-form" className="device-form" aria-label="Add device" aria-busy={busy} onSubmit={add}>
        <fieldset disabled={busy}>
          <div className="device-form-fields">
            <label>Device name<input autoFocus name="name" value={draft.name} onChange={field} maxLength={100} required placeholder="Living room sensor" /></label>
            <label>Room<input name="room" value={draft.room} onChange={field} maxLength={80} required placeholder="Living room" /></label>
            <label>Initial reading<input name="value" value={draft.value} onChange={field} maxLength={40} required /></label>
            <label>Sampling interval (seconds)<input type="number" name="poll_interval_seconds" value={draft.poll_interval_seconds} onChange={field} min={5} max={3600} required aria-describedby="sampling-help" /></label>
          </div>
          <p className="device-hint" id="sampling-help">Changes are sent immediately. Unchanged readings send a heartbeat after at least five minutes, on the next sampling turn.</p>
          {error && <p role="alert" className="task-error">{error}</p>}
          <button className="primary-button" type="submit">{busy ? 'Adding…' : 'Save device'}</button>
        </fieldset>
      </form>}
      {devices.length ? <div className="device-grid">{devices.map(device => <article className="device-card" key={device.id}>
        <div className="device-card-top"><span className="device-icon"><DeviceIcon name={device.name} /></span><span className={`device-state ${device.online ? 'online' : 'offline'}`}>{device.online ? <WifiHigh size={14} /> : <WifiSlash size={14} />}{device.online ? 'Online' : 'Offline'}</span></div>
        <h3>{device.name}</h3><p className="device-room">{device.room}</p>
        <div className="device-reading"><strong>{device.value}</strong><span>Every {device.poll_interval_seconds || 60}s</span></div>
      </article>)}</div> : <div className="empty-state"><Plug size={30} aria-hidden="true" /><h3>No devices connected</h3><p>Add a device to see its readings here.</p></div>}
      <p className="panel-footnote">Simulated devices with staggered sampling.</p>
    </section>
    <section className="panel signal-delivery" aria-labelledby="signal-heading">
      <div className="signal-overview">
        <span className="signal-icon"><PaperPlaneTilt size={24} aria-hidden="true" /></span>
        <h2 id="signal-heading">Signal delivery</h2><p>Device updates, delivered and accounted for.</p>
        {statsError && <p role="status" className="task-error">{statsError}</p>}
        {stats && <div className="signal-counts"><div><strong>{stats.depth}</strong><span>Pending</span></div><div><strong>{stats.delivered}</strong><span>Delivered</span></div></div>}
        <p className="device-hint">Pending signals stay saved until the receiver is available. Status refreshes every five seconds.</p>
      </div>
      <div className="signal-activity">
        <div className="activity-heading"><h3>Recent activity</h3><span>JSON via local HTTP</span></div>
        {stats ? stats.recent.length ? <>
          {(showAll ? stats.recent : stats.recent.slice(0, 3)).map(message => <details key={message.id} className="signal-message">
            <summary><span className={`delivery-icon ${message.delivered ? 'delivered' : 'pending'}`}>{message.delivered ? <CheckCircle size={20} /> : <Clock size={20} />}</span>
              <span className="signal-name">{message.payload.data.name}<small>{message.payload.data.value}</small></span>
              <span className="delivery-state">{message.delivered ? 'Delivered' : message.error ? 'Retry scheduled' : 'Pending'}</span><CaretDown className="disclosure-icon" size={16} aria-hidden="true" />
            </summary><pre aria-label={`JSON signal from ${message.payload.data.name}`}>{JSON.stringify(message.payload, null, 2)}</pre>
          </details>)}
          {stats.recent.length > 3 && <button type="button" className="text-button" onClick={() => setShowAll(!showAll)} aria-expanded={showAll}>{showAll ? 'Show less' : `Show all ${stats.recent.length} recent signals`}<CaretDown size={14} aria-hidden="true" /></button>}
        </> : <p className="empty-state">No signals yet. Add a device to send its first reading.</p> : !statsError && <div className="activity-skeleton" aria-label="Loading delivery status" aria-busy="true"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>}
      </div>
    </section>
  </>;
}
