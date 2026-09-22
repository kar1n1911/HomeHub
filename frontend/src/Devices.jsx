import { useEffect, useRef, useState } from 'react';

const initial = { name: '', room: '', value: 'Ready', poll_interval_seconds: 60 };
export default function Devices({ devices, onAdded }) {
  const [draft, setDraft] = useState(initial);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState('');
  const saving = useRef(false);
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
  async function add(event) {
    event.preventDefault();
    if (saving.current) return;
    if (!draft.name.trim() || !draft.room.trim()) { setError('Enter a device name and room.'); return; }
    saving.current = true; setBusy(true); setError(''); setNotice('');
    try {
      const response = await fetch('/api/devices', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...draft, poll_interval_seconds: Number(draft.poll_interval_seconds) }) });
      if (!response.ok) throw new Error(response.status === 503 ? 'Signal storage is busy. Please try again later.' : 'Could not add device. Check the fields and try again.');
      const device = await response.json();
      onAdded(device); setDraft(initial); setOpen(false); setNotice(`${device.name} added. Its first signal is queued for delivery.`);
    } catch (err) { setError(err instanceof TypeError ? 'Connection lost. Refresh to check whether the device was added before retrying.' : err.message); }
    finally { saving.current = false; setBusy(false); }
  }
  function field(event) { setDraft(current => ({ ...current, [event.target.name]: event.target.value })); }
  return <section className="panel devices-panel" id="devices">
    <div className="panel-heading"><div><h2>Devices</h2><p>Simulated devices · staggered sampling</p></div><button className="device-add" onClick={() => { setOpen(!open); setError(''); }} disabled={busy}>{open ? 'Cancel' : 'Add device'}</button></div>
    {notice && <p className="task-notice" role="status">{notice}</p>}
    {open && <form className="device-form" onSubmit={add}>
      <fieldset disabled={busy}>
        <label>Device name<input name="name" value={draft.name} onChange={field} maxLength={100} required placeholder="Living room sensor" /></label>
        <label>Room<input name="room" value={draft.room} onChange={field} maxLength={80} required placeholder="Living room" /></label>
        <label>Initial reading<input name="value" value={draft.value} onChange={field} maxLength={40} required /></label>
        <label>Sampling interval (seconds)<input type="number" name="poll_interval_seconds" value={draft.poll_interval_seconds} onChange={field} min={5} max={3600} required /></label>
        <p className="device-hint">Changes are sent immediately. Unchanged readings send a heartbeat after at least five minutes, on the next sampling turn.</p>
        <button className="device-add" type="submit">{busy ? 'Adding…' : 'Save device'}</button>
      </fieldset>
      {error && <p role="alert" className="task-error">{error}</p>}
    </form>}
    {devices.length ? devices.map(device => <article className="device-row" key={device.id}><span className={`device-icon ${device.online ? 'online' : 'offline'}`}>●</span><div><strong>{device.name}</strong><span>{device.room} · every {device.poll_interval_seconds || 60}s</span></div><span className="device-value">{device.value}</span></article>) : <p className="empty-state">No devices connected.</p>}
    <div className="signal-delivery"><h3>Signal delivery</h3><p>JSON → local HTTP receiver</p>
      {statsError && <p role="status" className="task-error">{statsError}</p>}
      {stats ? <><div className="signal-counts"><span><strong>{stats.depth}</strong> pending</span><span><strong>{stats.delivered}</strong> delivered</span></div>
        <p className="device-hint">Pending signals stay saved while the receiver is unavailable. Status updates every five seconds.</p>
        {stats.recent.map(message => <details key={message.id}><summary>{message.payload.data.name} · {message.delivered ? 'Delivered' : 'Pending'}{message.error ? ' · retry scheduled' : ''}</summary><pre>{JSON.stringify(message.payload, null, 2)}</pre></details>)}
      </> : !statsError && <p>Loading delivery status…</p>}
    </div>
  </section>;
}
