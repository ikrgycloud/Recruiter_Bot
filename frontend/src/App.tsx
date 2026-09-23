import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useOutletContext } from 'react-router-dom'
import './App.css'
import logo from './assets/logo.jpeg'

const API = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api').replace(/\/$/, '')
type User = { id: string; full_name: string; email: string; company_id: string; role: string }
type Session = { access_token: string; user: User }
type OverviewData = { user: User; metrics: { email_count: number; reschedule_count: number }; google_connected: boolean }
type AdminUserStatus = { id: string; full_name: string; email: string; role: string; status: string; google_connected: boolean; outlook_connected: boolean; permission_count: number; permissions: string[]; approval_state: string; last_updated: string | null }
type AdminAlert = { type: string; title: string; severity: string; message: string }
type AdminApproval = { user: string; email: string; role: string; status: string; systems: Array<string | null> }
type AdminOverview = { company: { id: string | null; name: string; total_users: number; admins: number; recruiters: number }; summary: { total_users: number; google_connected: number; outlook_connected: number; integration_coverage: number; permission_count: number; approval_count: number }; systems: { google: { connected_users: number; required_scopes: string[] }; outlook: { connected_users: number; required_scopes: string[] } }; users: AdminUserStatus[]; alerts: AdminAlert[]; approvals: AdminApproval[] }
type Message = { id: string; sender: string | null; subject: string | null; body_preview: string | null; received_at: string | null; classification: string; processed: boolean }
type CalendarEvent = { id: string; summary?: string; location?: string; status?: string; start: { dateTime?: string; date?: string; timeZone?: string }; end: { dateTime?: string; date?: string; timeZone?: string } }
type CalendarWeek = { timezone: string; week_start: string; week_end: string; events: CalendarEvent[] }
type GmailStatus = { connected: boolean; reconnect_required?: boolean; message?: string; email: string | null; message_count: number }
type GmailSyncResponse = { synced: number; new: number; existing: number; messages: Array<{ id: string; classification: string }> }
type PendingReschedule = { id: string; sender: string | null; subject: string | null; body_preview: string | null; status: 'ready' | 'needs_review'; reason?: string; event_id?: string; event_summary?: string; requested_date?: string; candidate_requested_date?: boolean; candidate_requested_time?: string; availability_date?: string; start?: string; end?: string; duration_seconds?: number; timezone?: string; used_next_available_date?: boolean }
type AutomationSettings = { automatic_rescheduling_enabled: boolean; sync_interval_seconds: number; default_mode: 'suggest_and_approve' | 'recruiter_selects' | string; working_days: number[]; shift_start: string; shift_end: string }
type Notification = { id: string; type: string; title: string; sender: string | null; subject: string; received_at: string | null; recorded_at: string | null }

async function api<T>(path: string, session: Session, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json', ...(options.headers ?? {}) } })
  const data = await readResponse<T & { detail?: string }>(response)
  if (!response.ok) throw new Error(data.detail ?? 'Request failed')
  return data
}

async function readResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  const contentType = response.headers.get('content-type') ?? ''

  if (!text) {
    throw new Error(`The backend returned an empty response (${response.status} ${response.statusText}) from ${response.url}. Check that the API is running and the VITE_API_URL matches http://localhost:8000/api.`)
  }

  if (!contentType.includes('application/json')) {
    throw new Error(`The backend responded with HTML instead of JSON (${response.status} ${response.statusText}) from ${response.url}. Check the backend URL or API server: ${API}`)
  }

  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(`The backend returned invalid JSON (${response.status} ${response.statusText}) from ${response.url}. Check the backend URL or API server: ${API}`)
  }
}

function App() { useEffect(() => { document.title = 'IKRGY Recruiting Automation'; let icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]'); if (!icon) { icon = document.createElement('link'); icon.rel = 'icon'; document.head.appendChild(icon) } icon.href = logo }, []); return <BrowserRouter><Routes><Route path="/login" element={<Login />} /><Route path="/register" element={<Register />} /><Route path="/privacy-policy" element={<PrivacyPolicy />} /><Route path="/terms-of-service" element={<TermsOfService />} /><Route path="/" element={<LandingPage />} /><Route path="/dashboard" element={<Protected />}><Route index element={<OverviewPage />} /><Route path="admin" element={<AdminOverviewPage />} /><Route path="rescheduling" element={<ReschedulingPage />} /><Route path="calendar" element={<CalendarPage />} /><Route path="approvals" element={<ApprovalsPage />} /><Route path="ranking" element={<RankingPage />} /><Route path="integrations" element={<IntegrationsPage />} /><Route path="audit" element={<AuditPage />} /><Route path="notifications" element={<NotificationsPage />} /><Route path="settings" element={<SettingsPage />} /></Route><Route path="*" element={<Navigate to="/" replace />} /></Routes></BrowserRouter> }

function LandingPage() { return <main className="landing-page"><header className="landing-nav"><Link className="landing-brand" to="/"><img src={logo} alt="IKRGY logo" /><span>IKRGY<br /><b>Recruiting Automation</b></span></Link><nav><Link to="/privacy-policy">Privacy</Link><Link to="/terms-of-service">Terms</Link><Link className="landing-login" to="/login">Sign in <span>↗</span></Link></nav></header><section className="landing-hero"><div className="landing-copy"><span className="eyebrow">The operating layer for modern recruiting</span><h1>Move candidates forward, <em>with control.</em></h1><p>IKRGY connects inbox signals, calendars, recruiter approvals, and communication tools in one clear workspace.</p><div className="landing-actions"><Link className="primary" to="/login">Enter workspace <span>→</span></Link><Link className="landing-text-link" to="/register">Create an account <span>↗</span></Link></div></div><div className="landing-orbit"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="landing-card"><img src={logo} alt="IKRGY" /><span>RECRUITING OPERATIONS</span><strong>Inbox to outcome.</strong><small>Human review stays in the loop.</small></div></div></section><section className="landing-features"><div className="feature-intro"><span className="eyebrow">One workspace</span><h2>Clarity for every handoff.</h2><p>Keep the system connected while keeping decisions with your recruiting team.</p></div><div className="feature-list"><Feature number="01" title="Connected signals" copy="Bring Gmail, Google Calendar, Outlook, and scheduling context together." /><Feature number="02" title="Approval-first workflows" copy="Review proposed actions before important candidate communication moves." /><Feature number="03" title="Recruiter-owned outcomes" copy="Automation assists the work. Your team remains the final decision-maker." /></div></section><footer className="landing-footer"><span>© 2026 IKRGY Recruiting Automation</span><LegalLinks /></footer></main> }

function Feature({ number, title, copy }: { number: string; title: string; copy: string }) { return <article className="feature"><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div></article> }

function Login() { const navigate = useNavigate(); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const submit = async (event: FormEvent) => { event.preventDefault(); setError(''); try { const response = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) }); const data = await readResponse<Session & { detail?: string }>(response); if (!response.ok) throw new Error(data.detail ?? 'Unable to login'); localStorage.setItem('recruiter-session', JSON.stringify(data)); navigate('/dashboard') } catch (e) { setError(e instanceof Error ? e.message : 'Unable to login') } }; return <main className="login-page"><form className="login-form" onSubmit={submit}><Link className="login-brand" to="/"><img src={logo} alt="IKRGY logo" /><span>IKRGY<br /><b>Recruiting Automation</b></span></Link><h1>Welcome back.</h1><p>Sign in to continue to your recruiting operations workspace.</p><label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>{error && <div className="error">{error}</div>}<button className="primary wide">Sign in <span>→</span></button><small>New to the workspace? <Link to="/register">Create an account</Link></small><LegalLinks /></form></main> }

function Register() { const navigate = useNavigate(); const [form, setForm] = useState({ full_name: '', company_email: '', password: '', confirm_password: '' }); const [error, setError] = useState(''); const update = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value })); const submit = async (event: FormEvent) => { event.preventDefault(); setError(''); try { const response = await fetch(`${API}/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) }); const data = await readResponse<Session & { detail?: string }>(response); if (!response.ok) throw new Error(data.detail ?? 'Unable to create account'); localStorage.setItem('recruiter-session', JSON.stringify(data)); navigate('/dashboard') } catch (e) { setError(e instanceof Error ? e.message : 'Unable to create account') } }; return <main className="login-page"><form className="login-form" onSubmit={submit}><Link className="login-brand" to="/"><img src={logo} alt="IKRGY logo" /><span>IKRGY<br /><b>Recruiting Automation</b></span></Link><h1>Create your account.</h1><p>Set up your recruiter workspace in a few simple steps.</p><label>Full name<input value={form.full_name} onChange={e => update('full_name', e.target.value)} required /></label><label>Work email<input type="email" value={form.company_email} onChange={e => update('company_email', e.target.value)} required /></label><label>Password<input type="password" value={form.password} onChange={e => update('password', e.target.value)} minLength={8} required /></label><label>Confirm password<input type="password" value={form.confirm_password} onChange={e => update('confirm_password', e.target.value)} minLength={8} required /></label>{error && <div className="error">{error}</div>}<button className="primary wide">Create account <span>→</span></button><small>Already registered? <Link to="/login">Sign in</Link></small><LegalLinks /></form></main> }

function LegalLinks() { return <div className="legal-links"><Link to="/privacy-policy">Privacy Policy</Link><span>·</span><Link to="/terms-of-service">Terms of Service</Link></div> }

function PrivacyPolicy() { return <LegalPage title="Privacy Policy"><h2>1. Overview</h2><p>This Privacy Policy explains how IKRGY Recruiting Automation collects, uses, stores, and protects information when you use the application.</p><h2>2. Information we collect</h2><p>We collect account details such as your name, work email, company information, and encrypted authentication data. When you connect a provider, we process the permissions and information needed to provide the requested Gmail, Google Calendar, Microsoft Outlook, email, and scheduling features.</p><h2>3. How we use information</h2><p>We use information to authenticate users, operate recruiting workflows, synchronize connected services, support calendar scheduling, communicate workflow results, maintain security, and improve reliability.</p><h2>4. Connected providers</h2><p>Provider access is initiated by you through the provider's authorization flow. We do not sell connected mailbox or calendar data. You can disconnect a provider from the Integrations area, subject to records that must be retained for security or legal purposes.</p><h2>5. Storage and security</h2><p>Credentials and provider tokens are protected using encryption at rest and access controls. No internet transmission or storage method can be guaranteed completely secure, so protect your account credentials and notify us of suspected unauthorized access.</p><h2>6. Retention and deletion</h2><p>We retain information while your account or connected workflows are active and as needed for security, dispute resolution, legal compliance, and operational records. Contact the application administrator to request account or data deletion.</p><h2>7. Contact</h2><p>For privacy questions or requests, contact the administrator associated with your IKRGY workspace.</p></LegalPage> }

function TermsOfService() { return <LegalPage title="Terms of Service"><h2>1. Acceptance</h2><p>By creating an account or using IKRGY Recruiting Automation, you agree to these Terms of Service and applicable law. If you do not agree, do not use the application.</p><h2>2. Account responsibilities</h2><p>You are responsible for providing accurate registration information, protecting your credentials, and all activity performed through your account. Notify your workspace administrator promptly about unauthorized access.</p><h2>3. Connected services</h2><p>You may connect supported Gmail, Google Calendar, and Microsoft Outlook accounts. You authorize the application to use only the permissions required for the features you select. Provider terms and policies also apply.</p><h2>4. Recruiting workflows</h2><p>The application provides operational assistance and recommendations. Recruiters and administrators remain responsible for reviewing outputs, approving actions, complying with employment laws, and making all hiring decisions. The application does not make hiring decisions on your behalf.</p><h2>5. Acceptable use</h2><p>Do not misuse the application, access another user's account, interfere with its operation, upload unlawful material, or use connected services without authorization.</p><h2>6. Availability and changes</h2><p>We may update, suspend, or improve features from time to time. We may update these terms when necessary and will publish the revised version through the application.</p><h2>7. Contact</h2><p>For questions about these terms, contact the administrator associated with your IKRGY workspace.</p></LegalPage> }

function LegalPage({ title, children }: { title: string; children: ReactNode }) { return <main className="legal-page"><header className="legal-header"><Link className="legal-brand" to="/login"><img src={logo} alt="IKRGY logo" /><span>IKRGY Recruiting Automation</span></Link><Link className="secondary" to="/login">Back to sign in</Link></header><article className="legal-content"><span className="eyebrow">IKRGY Recruiting Automation</span><h1>{title}</h1><p className="legal-updated">Effective date: September 17, 2026</p>{children}</article></main> }

function Protected() { const saved = localStorage.getItem('recruiter-session'); if (!saved) return <Navigate to="/login" replace />; return <Portal session={JSON.parse(saved)} /> }
function Portal({ session }: { session: Session }) { const navigate = useNavigate(); const location = useLocation(); const [data, setData] = useState<OverviewData>({ user: session.user, metrics: { email_count: 0, reschedule_count: 0 }, google_connected: false }); const [loading, setLoading] = useState(true); const refresh = async () => { try { const overview = await api<OverviewData>('/portal/overview', session); setData(overview); setLoading(false); } catch { setData({ user: session.user, metrics: { email_count: 0, reschedule_count: 0 }, google_connected: false }); setLoading(false); } }; useEffect(() => { void refresh(); }, [session.access_token, session.user.id]); const logout = () => { localStorage.removeItem('recruiter-session'); navigate('/login') }; const nav = session.user.role === 'admin' ? [['/dashboard/admin?tab=overview', 'Overview', '◫'], ['/dashboard/admin?tab=users', 'Users', '▣'], ['/dashboard/admin?tab=connections', 'Connections', '⛓'], ['/dashboard/admin?tab=notifications', 'Notifications', '◉'], ['/dashboard/admin?tab=settings', 'Settings', '⚙']] : [['/dashboard', 'Overview', '◫'], ['/dashboard/rescheduling', 'Mails', '↻'], ['/dashboard/calendar', 'Calendar', '◫'], ['/dashboard/approvals', 'Approval Queue', '✓'],  ['/dashboard/integrations', 'Integrations', '⛓'], ['/dashboard/notifications', 'Notifications', '◉'], ['/dashboard/settings', 'Settings', '⚙']]; return <div className="app-shell"><aside className="sidebar"><Link className="brand" to="/dashboard"><img src={logo} alt="IKRGY logo" /><span><b>IKRGY</b>Recruiting Automation</span></Link><div className="env-chip">database mode · live</div><nav>{nav.map(([path, label, icon]) => { const routePath = path.split('?')[0]; const isActive = location.pathname === routePath && (path.includes('tab=') ? location.search.includes('tab=') : true); return <Link className={`nav-link ${isActive ? 'active' : ''}`} to={path} key={path}><i>{icon}</i>{label}</Link> })}</nav><div className="sidebar-foot"><div className="security-note"><b>{data.user.role === 'admin' ? 'Admin-controlled' : 'Recruiter-controlled'}</b><span>{data.user.role === 'admin' ? 'Operational oversight & access review.' : 'No automatic hiring decisions.'}</span></div><button className="ghost full" onClick={logout}>Sign out</button></div></aside><main className="main"><header className="topbar"><div><h1>{titleFor(location.pathname)}</h1><p>{data.user.role === 'admin' ? 'Operational oversight for the full workspace' : 'Live operating view for the recruiting automation platform'}</p></div><div className="top-actions"><span className="live-dot" /> {data.user.full_name} <span className="role-pill">{data.user.role}</span></div></header><section className="content"><Outlet context={{ session, data: loading ? null : data, refresh }} /></section></main></div> }
function titleFor(path: string) { const value = path.split('/').pop(); return ({ dashboard: 'Recruiting Operations', admin: 'Admin Command Center', rescheduling: 'Workflow 1 · Candidate Rescheduling', calendar: 'Google Calendar', approvals: 'Approval Queue', ranking: 'Workflow 2 · Candidate Ranking & Recruiter Alert', integrations: 'Integrations', audit: 'Audit & Observability', notifications: 'Notifications', settings: 'Rescheduling Settings' } as Record<string, string>)[value ?? 'dashboard'] }

function AdminOverviewPage() {
  const { session } = useOutletData();
  const location = useLocation();
  const [data, setData] = useState<AdminOverview | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const sessionKey = session ? `${session.access_token}:${session.user.id}` : null
  const adminTab = new URLSearchParams(location.search).get('tab') ?? 'overview'
  const activeTab = ['overview', 'users', 'connections', 'approvals', 'notifications', 'audit', 'settings'].includes(adminTab) ? adminTab : 'overview'
  const [usersPage, setUsersPage] = useState(1)
  const [connectionsPage, setConnectionsPage] = useState(1)
  const pageSize = 6

  useEffect(() => {
    if (!session) return
    ;(async () => {
      try {
        setLoading(true)
        const overview = await api<AdminOverview>('/portal/admin/overview', session)
        setData(overview)
        setError('')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unable to load admin overview')
      } finally {
        setLoading(false)
      }
    })()
  }, [sessionKey])

  if (!session) return <Loading />
  if (loading) return <Loading />
  if (error) return <Panel title="Admin workspace unavailable" subtitle="Connection issue"><div className="error">{error}</div></Panel>
  if (!data) return <Loading />

  const renderOverview = () => (
    <>
      <div className="admin-summary-grid">
        <Kpi label="Total users" value={data.summary.total_users} tone="cyan" />
        <Kpi label="Google connected" value={data.summary.google_connected} tone="green" />
        <Kpi label="Outlook connected" value={data.summary.outlook_connected} tone="orange" />
        <Kpi label="Permission set" value={data.summary.permission_count} tone="violet" />
      </div>

      <div className="grid-2">
        <Panel title="Workspace health" subtitle="Operational coverage and connected systems">
          <div className="admin-metrics">
            <div><span>Coverage</span><strong>{data.summary.integration_coverage}%</strong></div>
            <div><span>Approval queue</span><strong>{data.summary.approval_count}</strong></div>
            <div><span>Admins</span><strong>{data.company.admins}</strong></div>
            <div><span>Recruiters</span><strong>{data.company.recruiters}</strong></div>
          </div>
        </Panel>
        <Panel title="System requirements" subtitle="Connected user counts and permission scopes">
          <div className="system-list">
            <div className="system-row"><div><b>Google Workspace</b><small>{data.systems.google.connected_users} users connected</small></div><span className="badge">{data.systems.google.required_scopes.length} scopes</span></div>
            <div className="system-row"><div><b>Microsoft Outlook</b><small>{data.systems.outlook.connected_users} users connected</small></div><span className="badge">{data.systems.outlook.required_scopes.length} scopes</span></div>
          </div>
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Access alerts" subtitle="Current operational issues and review items">
          <div className="alert-list">
            {data.alerts.map((alert) => (
              <div className={`alert-row alert-${alert.severity}`} key={`${alert.type}-${alert.title}`}>
                <div><b>{alert.title}</b><small>{alert.message}</small></div>
                <span className="badge">{alert.severity}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Approval status" subtitle="Systems approved for live workflows">
          <div className="approval-list">
            {data.approvals.map((approval) => (
              <div className="approval-row" key={`${approval.email}-${approval.role}`}>
                <div>
                  <b>{approval.user}</b>
                  <small>{approval.email}</small>
                </div>
                <div className="approval-meta">
                  <span className="badge">{approval.status}</span>
                  <span>{(approval.systems.filter(Boolean) as string[]).join(' · ') || 'No system approved yet'}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  )

  const directoryUsers = data.users.filter(user => user.role !== 'admin')
  const usersTotalPages = Math.max(1, Math.ceil(directoryUsers.length / pageSize))
  const currentUsersPage = Math.min(usersPage, usersTotalPages)
  const usersStart = (currentUsersPage - 1) * pageSize
  const pagedUsers = directoryUsers.slice(usersStart, usersStart + pageSize)

  const renderUsers = () => (
    <Panel title="All users" subtitle="Every account in the database with connection and permission details">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Google</th>
              <th>Outlook</th>
              <th>Permissions</th>
              <th>Approval</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {pagedUsers.map((user) => (
              <tr key={user.id}>
                <td>
                  <strong>{user.full_name}</strong>
                  <small>{user.email}</small>
                </td>
                <td><span className="badge">{user.role}</span></td>
                <td>{user.google_connected ? 'Connected' : 'Not connected'}</td>
                <td>{user.outlook_connected ? 'Connected' : 'Not connected'}</td>
                <td>
                  <div className="permission-stack">
                    {user.permissions.length ? user.permissions.map((permission) => <span key={`${user.id}-${permission}`} className="mini-pill">{permission}</span>) : <span className="muted">No scopes granted</span>}
                  </div>
                </td>
                <td><span className={`badge approval-badge ${user.approval_state === 'approved' ? 'approved' : 'pending'}`}>{user.approval_state}</span></td>
                <td>{user.last_updated ? formatSystemTimestamp(user.last_updated) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
        <button className="secondary" onClick={() => setUsersPage((p) => Math.max(1, p - 1))} disabled={currentUsersPage === 1}>Previous</button>
        <span>Page {currentUsersPage} of {usersTotalPages}</span>
        <button className="secondary" onClick={() => setUsersPage((p) => Math.min(usersTotalPages, p + 1))} disabled={currentUsersPage === usersTotalPages}>Next</button>
      </div>
    </Panel>
  )

  const connectionsTotalPages = Math.max(1, Math.ceil(directoryUsers.length / pageSize))
  const currentConnectionsPage = Math.min(connectionsPage, connectionsTotalPages)
  const connectionsStart = (currentConnectionsPage - 1) * pageSize
  const pagedConnections = directoryUsers.slice(connectionsStart, connectionsStart + pageSize)

  const renderConnections = () => (
    <Panel title="User connection status" subtitle="Connection inventory for every account">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Google</th>
              <th>Outlook</th>
              <th>Permissions</th>
              <th>Last updated</th>
            </tr>
          </thead>
          <tbody>
            {pagedConnections.map((user) => (
              <tr key={`conn-${user.id}`}>
                <td>
                  <strong>{user.full_name}</strong>
                  <small>{user.email}</small>
                </td>
                <td><span className="badge">{user.role}</span></td>
                <td><span className={`badge ${user.google_connected ? 'approved' : 'pending'}`}>{user.google_connected ? 'Connected' : 'Not connected'}</span></td>
                <td><span className={`badge ${user.outlook_connected ? 'approved' : 'pending'}`}>{user.outlook_connected ? 'Connected' : 'Not connected'}</span></td>
                <td>
                  <div className="permission-stack">
                    {user.permissions.length ? user.permissions.map((permission) => <span key={`${user.id}-perm-${permission}`} className="mini-pill">{permission}</span>) : <span className="muted">No scopes</span>}
                  </div>
                </td>
                <td>{user.last_updated ? formatSystemTimestamp(user.last_updated) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
        <button className="secondary" onClick={() => setConnectionsPage((p) => Math.max(1, p - 1))} disabled={currentConnectionsPage === 1}>Previous</button>
        <span>Page {currentConnectionsPage} of {connectionsTotalPages}</span>
        <button className="secondary" onClick={() => setConnectionsPage((p) => Math.min(connectionsTotalPages, p + 1))} disabled={currentConnectionsPage === connectionsTotalPages}>Next</button>
      </div>
    </Panel>
  )

  const renderApprovals = () => (
    <Panel title="Approval queue" subtitle="Current approval status for all users">
      <div className="approval-list">
        {data.approvals.map((approval) => (
          <div className="approval-row" key={`${approval.email}-${approval.role}`}>
            <div>
              <b>{approval.user}</b>
              <small>{approval.email}</small>
            </div>
            <div className="approval-meta">
              <span className="badge">{approval.status}</span>
              <span>{(approval.systems.filter(Boolean) as string[]).join(' · ') || 'No system approved yet'}</span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  )

  const renderNotifications = () => (
    <Panel title="Notifications" subtitle="Workspace alerts and review items">
      <div className="alert-list">
        {data.alerts.map((alert) => (
          <div className={`alert-row alert-${alert.severity}`} key={`${alert.type}-${alert.title}`}>
            <div><b>{alert.title}</b><small>{alert.message}</small></div>
            <span className="badge">{alert.severity}</span>
          </div>
        ))}
      </div>
    </Panel>
  )

  const renderAudit = () => (
    <Panel title="Audit logs" subtitle="Operational record trail for access, approvals, and system state">
      <div className="alert-list">
        {data.users.length ? data.users.map((user) => (
          <div className="alert-row" key={`audit-${user.id}`}>
            <div>
              <b>{user.full_name}</b>
              <small>{user.email} · {user.role} · {user.approval_state}</small>
            </div>
            <span className="badge">{user.google_connected ? 'Google connected' : 'Google missing'}</span>
          </div>
        )) : <div className="empty"><span>◌</span>No audit entries available.</div>}
      </div>
    </Panel>
  )

  const renderSettings = () => (
    <Panel title="Workspace access" subtitle="Current admin account and installation details">
      <div className="settings">
        <div><span>Role</span><b>{session.user.role}</b></div>
        <div><span>Google connection</span><b>{data.summary.google_connected > 0 ? 'Visible in workspace' : 'Not connected by any user'}</b></div>
        <div><span>Outlook connection</span><b>{data.summary.outlook_connected > 0 ? 'Visible in workspace' : 'Not connected by any user'}</b></div>
      </div>
    </Panel>
  )

  return <>
    <PageIntro kicker="Administration" title="Admin command center." copy="Review workspace health, access coverage, connected systems, permissions, approvals, and operational risks from one overview." />

    {activeTab === 'overview' && renderOverview()}
    {activeTab === 'users' && renderUsers()}
    {activeTab === 'connections' && renderConnections()}
    {activeTab === 'approvals' && renderApprovals()}
    {activeTab === 'notifications' && renderNotifications()}
    {activeTab === 'audit' && renderAudit()}
    {activeTab === 'settings' && renderSettings()}
  </>
}

function OverviewPage() { const { data } = useOutletData(); if (!data) return <Loading />; if (data.user.role === 'admin') return <AdminOverviewPage />; return <><section className="hero-strip"><div><span className="eyebrow">Shared platform spine</span><h2>Two workflows. One controlled recruiting platform.</h2><p>Live data from your account and connected communication systems.</p></div><div className="hero-actions"><Link className="primary" to="/dashboard/rescheduling">Open mails</Link><Link className="secondary" to="/dashboard/calendar">Open calendar</Link></div></section><div className="kpi-grid"><Kpi label="Synced emails" value={data.metrics.email_count} tone="cyan" /><Kpi label="Reschedule requests" value={data.metrics.reschedule_count} tone="violet" /><Kpi label="Google connected" value={data.google_connected ? 'Yes' : 'No'} tone="orange" /><Kpi label="Integrations" value="Manage" tone="green" /></div><div className="grid-2"><Panel title="Workflow health" subtitle="Runtime stages and control gates"><div className="workflow"><Workflow label="Inbox → calendar → approval → reply" /><Workflow label="Recruiter review remains final" alt /></div></Panel><Panel title="Connected systems" subtitle="Manage communication providers"><div className="list"><div className="list-row"><span className={`status-dot ${data.google_connected ? 'running' : 'offline'}`} /><div><b>Google Workspace</b><small>{data.google_connected ? 'Gmail and Calendar connected' : 'Connect Gmail and Calendar in Integrations'}</small></div><Link className="badge" to="/dashboard/integrations">Manage</Link></div><div className="list-row"><span className="status-dot offline" /><div><b>Microsoft Outlook</b><small>Connect from Integrations when configured</small></div><Link className="badge" to="/dashboard/integrations">Manage</Link></div></div></Panel></div></> }
function ReschedulingPage() {
  const { session } = useOutletData()
  const [messages, setMessages] = useState<Message[]>([])
  const [gmail, setGmail] = useState<GmailStatus | null>(null)
  const [status, setStatus] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [page, setPage] = useState(1)
  const pageSize = 25
  const [totalMessages, setTotalMessages] = useState(0)
  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(null)
  const [previewBody, setPreviewBody] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')

  const load = async () => {
    if (!session) return
    try {
      const [statusData, messageData] = await Promise.all([
        api<GmailStatus>('/integrations/google/gmail/status', session),
        api<{ items: Message[]; total: number }>(`/integrations/google/gmail/messages?page=${page}&page_size=${pageSize}`, session),
      ])
      setGmail(statusData)
      setMessages(messageData.items)
      setTotalMessages(messageData.total)
      setStatus('')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to load Gmail')
    }
  }

  useEffect(() => { void load() }, [session?.access_token, session?.user.id, page])

  const openPreview = async (message: Message) => {
    if (!session) return
    setExpandedMessageId(message.id)
    setPreviewBody('')
    setPreviewError('')
    setPreviewLoading(true)
    try {
      const result = await api<{ body: string; classification: string }>(`/integrations/google/gmail/messages/${message.id}/body`, session)
      setPreviewBody(result.body)
      setMessages(current => current.map(item => item.id === message.id
        ? { ...item, body_preview: result.body, classification: result.classification }
        : item))
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : 'Unable to load this email from Gmail')
    } finally {
      setPreviewLoading(false)
    }
  }

  const sync = async () => {
    if (!session) return
    setSyncing(true)
    setStatus('')
    try {
      const result = await api<GmailSyncResponse>('/integrations/google/gmail/sync?max_results=25', session, { method: 'POST' })
      await load()
      setStatus(`Gmail sync complete: ${result.new} new message${result.new === 1 ? '' : 's'} imported.`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to sync Gmail')
    } finally {
      setSyncing(false)
    }
  }

  if (!session) return <Loading />
  const rescheduleCount = messages.filter(message => message.classification === 'reschedule_request').length
  const pages = Math.max(1, Math.ceil(totalMessages / pageSize))
  return <>
    <PageIntro kicker="Workflow 1 · Step 1" title="Inbox signals." copy="Review Gmail messages and open the full body of reschedule requests." />
    <div className="sync-toolbar"><div><span className={`status-dot ${gmail?.connected ? 'running' : 'offline'}`} /><strong>{gmail?.connected ? `Connected${gmail.email ? ` · ${gmail.email}` : ''}` : gmail?.reconnect_required ? 'Google reconnect required' : 'Google account not connected'}</strong><small>{totalMessages || gmail?.message_count || 0} messages stored in this workspace</small></div>
      <div className="sync-actions"><button className="secondary" onClick={() => void load()}>Refresh inbox</button><Link className="secondary" to="/dashboard/integrations">Manage connection</Link><button className="primary" onClick={() => void sync()} disabled={!gmail?.connected || syncing}>{syncing ? 'Syncing…' : 'Sync Gmail'}</button></div>
    </div>
    {gmail?.reconnect_required && <div className="error banner">Google access expired or was revoked. Reconnect Google in <Link to="/dashboard/integrations">Integrations</Link> to resume inbox syncing.</div>}
    {status && <div className="sync-result">{status}</div>}
    <Panel title="Mailbox" subtitle={`Complete mail list with ${rescheduleCount} reschedule request${rescheduleCount === 1 ? '' : 's'}`}>
      <div className="table-wrap"><table><thead><tr><th>From</th><th>Subject</th><th>Classification</th><th>Preview</th><th>Received ({systemZoneLabel()})</th></tr></thead>
        <tbody>{messages.length ? messages.map(message => {
          const isReschedule = message.classification === 'reschedule_request'
          return <tr key={message.id}><td>{message.sender || 'Unknown sender'}</td><td>{message.subject || 'No subject'}</td><td><span className="badge">{message.classification}</span></td>
            <td><div className="mail-preview-cell">{isReschedule ? <><button className="secondary" type="button" onClick={() => expandedMessageId === message.id ? setExpandedMessageId(null) : void openPreview(message)}>{expandedMessageId === message.id ? 'Hide preview' : 'Preview'}</button>
              {expandedMessageId === message.id && <div className="mail-preview">{previewLoading ? 'Loading full email from Gmail…' : previewError || previewBody.trim() || 'Gmail did not return readable body text. This message may contain attachments only.'}</div>}</> : <span className="muted">No preview</span>}</div></td>
            <td>{message.received_at ? formatSystemTimestamp(message.received_at) : '—'}</td></tr>
        }) : <tr><td colSpan={5}><Empty text="No emails found yet." /></td></tr>}</tbody>
      </table></div>
      {totalMessages > 0 && <div className="pagination" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
        <button className="secondary" onClick={() => setPage(value => Math.max(1, value - 1))} disabled={page === 1}>Previous</button>
        <span>Page {page} of {pages}</span>
        <button className="secondary" onClick={() => setPage(value => Math.min(pages, value + 1))} disabled={page >= pages}>Next</button>
      </div>}
    </Panel>
  </>
}

function CalendarPage() {
  const { session } = useOutletData()
  const location = useLocation()
  const [weekOffset, setWeekOffset] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const [week, setWeek] = useState<CalendarWeek | null>(null)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')
  const displayZone = systemDisplayZone()
  const requestedDate = new URLSearchParams(location.search).get('date')

  useEffect(() => {
    setWeekOffset(calendarWeekOffset(requestedDate, displayZone))
  }, [requestedDate, displayZone])

  useEffect(() => {
    if (!session) return
    setLoading(true)
    void api<CalendarWeek>('/integrations/google/calendar/week?offset=' + weekOffset + '&display_timezone=' + encodeURIComponent(displayZone), session)
      .then(result => { setWeek(result); setStatus('') })
      .catch(error => setStatus(error instanceof Error ? error.message : 'Unable to load calendar'))
      .finally(() => setLoading(false))
  }, [session?.access_token, session?.user.id, weekOffset, refreshKey, displayZone])

  if (!session) return <Loading />
  const days = week ? Array.from({ length: 7 }, (_, index) => {
    const date = new Date(week.week_start + 'T00:00:00.000Z')
    date.setUTCDate(date.getUTCDate() + index)
    return date.toISOString().slice(0, 10)
  }) : []
  const timezone = week?.timezone ?? 'UTC'
  const hours = Array.from({ length: 24 }, (_, index) => index)
  const eventDate = (event: CalendarEvent) => event.start.date ?? (event.start.dateTime ? calendarDateKey(event.start.dateTime, timezone) : '')
  const dayEvents = (day: string) => week?.events.filter(event => eventDate(event) === day && !event.start.date) ?? []
  const allDayEvents = (day: string) => week?.events.filter(event => eventDate(event) === day && Boolean(event.start.date)) ?? []
  const weekLabel = week ? formatCalendarDate(week.week_start) + ' – ' + formatCalendarDate(week.week_end) : 'Loading week'

  return <>
    <PageIntro kicker="Workflow 1 · Step 2" title="Google Calendar." copy={'Live events from your primary Google Calendar. Times use ' + systemZoneLabel() + ' on this system.'} />
    <div className="calendar-toolbar">
      <div className="calendar-week-navigation">
        <button className="secondary" onClick={() => setWeekOffset(value => value - 1)} aria-label="Previous week">←</button>
        <button className="secondary" onClick={() => setWeekOffset(0)}>Today</button>
        <button className="secondary" onClick={() => setWeekOffset(value => value + 1)} aria-label="Next week">→</button>
        <strong>{weekLabel}</strong>
      </div>
      <button className="secondary" onClick={() => setRefreshKey(value => value + 1)}>Refresh calendar</button>
    </div>
    {status && <div className="error banner">{status}</div>}
    <Panel title="Week view" subtitle={'24-hour schedule · ' + timezone}>
      {loading && !week ? <Loading /> : week && <div className="calendar-week-scroll">
        <div className="calendar-week-grid">
          <div className="calendar-week-header">
            <div className="calendar-corner" />
            {days.map(day => <div className={'calendar-day-heading ' + (day === calendarDateKey(new Date().toISOString(), timezone) ? 'today' : '')} key={day}>
              <span>{formatCalendarWeekday(day)}</span><b>{formatCalendarDate(day)}</b>
            </div>)}
          </div>
          <div className="calendar-all-day-row">
            <div className="calendar-all-day-label">All day</div>
            {days.map(day => <div className="calendar-all-day-cell" key={day}>{allDayEvents(day).map(event =>
              <div className="calendar-all-day-event" key={event.id}>{event.summary || 'Untitled event'}</div>
            )}</div>)}
          </div>
          <div className="calendar-week-body">
            <div className="calendar-hour-labels">{hours.map(hour =>
              <div className="calendar-hour-label" key={hour}>{formatCalendarHour(hour)}</div>
            )}</div>
            <div className="calendar-day-columns">{days.map(day => <div className="calendar-day-column" key={day}>
              <div className="calendar-hour-lines" />
              {dayEvents(day).map(event => {
                const start = event.start.dateTime ? calendarMinutes(event.start.dateTime, timezone) : 0
                const rawEnd = event.end.dateTime ? calendarMinutes(event.end.dateTime, timezone) : start + 60
                const end = Math.max(start + 30, rawEnd > start ? rawEnd : 1440)
                const top = start * (64 / 60)
                const height = Math.max(30, Math.min(1440, end) - start) * (64 / 60)
                return <article className="calendar-event" key={event.id} style={{ top, height }} title={(event.summary || 'Untitled event') + ' · ' + (event.start.dateTime ? formatCalendarTime(event.start.dateTime, timezone) : '')}>
                  <b>{event.summary || 'Untitled event'}</b>
                  <span>{event.start.dateTime ? formatCalendarTime(event.start.dateTime, timezone) : ''}{event.end.dateTime ? ' – ' + formatCalendarTime(event.end.dateTime, timezone) : ''}</span>
                  {event.location && <small>{event.location}</small>}
                </article>
              })}
              {dayEvents(day).length === 0 && <span className="calendar-empty-day" aria-label="No meetings" />}
            </div>)}</div>
          </div>
        </div>
      </div>}
    </Panel>
  </>
}

function calendarDateKey(value: string, timezone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(value))
  const part = (type: string) => parts.find(item => item.type === type)?.value ?? '00'
  return part('year') + '-' + part('month') + '-' + part('day')
}
function calendarWeekOffset(targetDate: string | null, timezone: string) {
  if (!targetDate) return 0
  const monday = (value: Date) => {
    const day = new Date(value)
    day.setUTCHours(0, 0, 0, 0)
    day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7))
    return day
  }
  const target = new Date(targetDate + 'T12:00:00.000Z')
  const today = new Date(calendarDateKey(new Date().toISOString(), timezone) + 'T12:00:00.000Z')
  return Math.round((monday(target).getTime() - monday(today).getTime()) / (7 * 24 * 60 * 60 * 1000))
}
function calendarMinutes(value: string, timezone: string) {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(value))
  const part = (type: string) => Number(parts.find(item => item.type === type)?.value ?? 0)
  return part('hour') * 60 + part('minute')
}
function formatCalendarTime(value: string, timezone: string) {
  return new Date(value).toLocaleTimeString(undefined, { timeZone: timezone, hour: 'numeric', minute: '2-digit' })
}
function systemDisplayZone() {
  const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone
  return localZone === 'Asia/Kolkata' || localZone === 'Asia/Calcutta' ? 'Asia/Kolkata' : 'UTC'
}
function systemZoneLabel() { return systemDisplayZone() === 'Asia/Kolkata' ? 'IST' : 'UTC' }
function formatSystemTimestamp(value: string | Date) {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    timeZone: systemDisplayZone(),
  }).format(new Date(value)) + ' ' + systemZoneLabel()
}
function formatSystemTime(value: Date) {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric', minute: '2-digit', timeZone: systemDisplayZone(),
  }).format(value) + ' ' + systemZoneLabel()
}
function formatCalendarDate(value: string) {
  return new Date(value + 'T12:00:00.000Z').toLocaleDateString(undefined, { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' })
}
function formatCalendarWeekday(value: string) {
  return new Date(value + 'T12:00:00.000Z').toLocaleDateString(undefined, { timeZone: 'UTC', weekday: 'short' })
}
function formatCalendarHour(value: number) {
  return new Date(Date.UTC(2024, 0, 1, value)).toLocaleTimeString(undefined, { timeZone: 'UTC', hour: 'numeric' })
}
function ApprovalsPage() {
  const { session } = useOutletData()
  const [items, setItems] = useState<PendingReschedule[]>([])
  const [settings, setSettings] = useState<AutomationSettings | null>(null)
  const [dates, setDates] = useState<Record<string, string>>({})
  const [times, setTimes] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const [calendarEventUrl, setCalendarEventUrl] = useState('')
  const [calendarEventDate, setCalendarEventDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [previewId, setPreviewId] = useState<string | null>(null)

  const load = async () => {
    if (!session) return
    try {
      const [pending, automation] = await Promise.all([
        api<PendingReschedule[]>('/integrations/google/automation/pending', session),
        api<AutomationSettings>('/integrations/google/automation/settings', session),
      ])
      setItems(pending)
      setSettings(automation)
      setErrors(current => { const next = { ...current }; delete next.page; return next })
    } catch (e) {
      setErrors({ page: e instanceof Error ? e.message : 'Unable to load reschedule requests' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [session?.access_token, session?.user.id])

  const act = async (item: PendingReschedule, action: 'approve' | 'decline') => {
    if (!session) return
    setErrors(current => ({ ...current, [item.id]: '' }))
    setCalendarEventUrl('')
    setCalendarEventDate('')
    try {
      const options: RequestInit = { method: 'POST' }
      if (action === 'approve') {
        const payload: Record<string, string> = {}
        if (item.status === 'ready' && item.start && item.end) {
          payload.start = item.start
          payload.end = item.end
        } else {
          payload.date = dates[item.id] ?? item.requested_date ?? ''
          payload.time = times[item.id] ?? ''
        }
        if (item.status !== 'ready' && (!payload.date || !payload.time)) {
          setErrors(current => ({ ...current, [item.id]: 'Choose a date and time to approve this request.' }))
          return
        }
        options.body = JSON.stringify(payload)
      }
      const result = await api<{ status?: string; candidate_notified?: boolean; notification_error?: string; google_calendar_event_url?: string; start?: string }>('/integrations/google/automation/review/' + item.id + '/' + action, session, options)
      await load()
      setCalendarEventUrl(result.google_calendar_event_url || '')
      setCalendarEventDate(result.start || '')
      if (result.notification_error) setNotice(result.notification_error)
      else if (result.status === 'rescheduled' && result.candidate_notified) {
        setNotice('Interview updated in Google Calendar. A confirmation email was sent from your connected Google account.')
      } else if (result.status === 'rescheduled') {
        setNotice('Interview updated in Google Calendar, but the candidate email could not be confirmed.')
      } else if (result.status === 'declined') setNotice('Reschedule request dismissed.')
    } catch (e) {
      setErrors(current => ({ ...current, [item.id]: e instanceof Error ? e.message : 'Unable to update request' }))
    }
  }

  if (loading) return <Loading />
  return <>
    <PageIntro kicker="Reschedule requests" title="Review calendar changes." copy="The app checks the candidate’s requested date first. If it is unavailable or no date was given, it looks for the next free weekday slot while preserving the event duration and time zone." />
    {settings && <div className="sync-result">Automatic time suggestions are {settings.automatic_rescheduling_enabled ? 'ON' : 'OFF'}. {settings.automatic_rescheduling_enabled ? 'The app proposes an available slot; the meeting changes only after you approve it below.' : 'Choose a date and time for each request. The meeting changes only after you approve it.'}</div>}
    {notice && <div className={notice.includes('could not') ? 'error banner' : 'sync-result'}>{notice}</div>}
    {calendarEventUrl && <div className="sync-actions" style={{ marginBottom: 16 }}><Link className="secondary" to={calendarEventDate ? '/dashboard/calendar?date=' + calendarDateKey(calendarEventDate, systemDisplayZone()) : '/dashboard/calendar'}>View in app calendar</Link><a className="secondary" href={calendarEventUrl} target="_blank" rel="noreferrer">Open updated event in Google Calendar</a></div>}
    {errors.page && <div className="error banner">{errors.page}</div>}
    <div className="sync-actions" style={{ marginBottom: 16 }}><button className="secondary" onClick={() => void load()}>Refresh requests</button></div>
    <div className="approval-list">
      {items.length ? items.map(item => {
        const proposedStart = item.start ? new Date(item.start) : null
        const proposedEnd = item.end ? new Date(item.end) : null
        const dateValue = dates[item.id] ?? item.availability_date ?? item.requested_date ?? ''
        const proposedClock = proposedStart ? new Intl.DateTimeFormat('en-GB', { timeZone: item.timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(proposedStart) : settings?.shift_start || '09:00'
        const timeValue = times[item.id] ?? proposedClock
        const shiftLabel = settings ? `${settings.shift_start}–${settings.shift_end} ${item.timezone || 'UTC'}` : `Configured shift · ${item.timezone || 'UTC'}`
        return <article className="card" key={item.id}>
          <div className="card-head"><div><h3>{item.subject || 'Interview reschedule request'}</h3><p>{item.sender || 'Unknown sender'} · {item.event_summary || 'Calendar review needed'}</p></div><span className={'badge ' + (item.status === 'ready' ? 'approved' : 'pending')}>{item.status === 'ready' ? 'Ready' : 'Needs review'}</span></div>
          <div className="approval-schedule-grid"><div><span>Candidate request</span><b>{item.requested_date || 'No date specified'}{item.candidate_requested_time ? ` · ${item.candidate_requested_time}` : ''}</b></div><div><span>Working shift</span><b>{shiftLabel}</b></div><div className="approval-estimate"><span>Estimated schedule</span><b>{proposedStart && proposedEnd ? `${formatSystemTimestamp(proposedStart)} to ${formatSystemTime(proposedEnd)}` : 'Select a date and time'}</b><small>{item.used_next_available_date ? `Next available slot after ${item.requested_date || 'the requested date'}` : 'Checks calendar conflicts before saving'}</small></div></div>
          {item.body_preview && <button className="secondary approval-preview-toggle" type="button" onClick={() => setPreviewId(previewId === item.id ? null : item.id)}>{previewId === item.id ? 'Hide email preview' : 'Preview email'}</button>}
          {previewId === item.id && item.body_preview && <div className="approval-preview"><strong>Email request</strong><p>{item.body_preview}</p></div>}
          {item.status !== 'ready' && <><p>{item.reason || 'Select a time for this reschedule.'}</p><div className="sync-actions"><label>New date<input type="date" value={dateValue} onChange={event => setDates(current => ({ ...current, [item.id]: event.target.value }))} /></label><label>Start time<input type="time" value={timeValue} onChange={event => setTimes(current => ({ ...current, [item.id]: event.target.value }))} /></label></div><small>Enter the time in the event time zone: {item.timezone || 'UTC'}.</small></>}
          {errors[item.id] && <div className="error">{errors[item.id]}</div>}
          <div className="sync-actions" style={{ marginTop: 16 }}>
            {item.status === 'ready' && <button className="primary" onClick={() => void act(item, 'approve')}>Approve and reschedule</button>}
            {item.status !== 'ready' && <button className="primary" disabled={!item.event_id} onClick={() => void act(item, 'approve')}>Use selected time</button>}
            <button className="secondary" onClick={() => void act(item, 'decline')}>Dismiss request</button>
          </div>
          {!item.event_id && <div><small>Review the related calendar invitation to link this request before approving the suggested time.</small><div className="sync-actions"><Link className="secondary" to={item.start ? '/dashboard/calendar?date=' + calendarDateKey(item.start, systemDisplayZone()) : '/dashboard/calendar'}>Open app calendar</Link></div></div>}
        </article>
      }) : <Panel title="No pending requests" subtitle="New Gmail messages are checked in the background"><Empty text="There are no reschedule requests waiting for review." /></Panel>}
    </div>
  </>
}
function RankingPage() { return <><PageIntro kicker="Workflow 2" title="Ranking and recruiter alerts." copy="Candidate rankings will appear here once requisition and applicant APIs are connected." /><Panel title="Active requisitions" subtitle="Database-backed records only"><Empty text="No requisitions available from the backend yet." /></Panel></> }
function IntegrationsPage() { const { session, data } = useOutletData(); const location = useLocation(); if (!session) return <Loading />; const [googleConnected, setGoogleConnected] = useState(Boolean(data?.google_connected)); const [googleReconnectRequired, setGoogleReconnectRequired] = useState(false); const [outlookConnected, setOutlookConnected] = useState(false); const [status, setStatus] = useState(''); useEffect(() => { const params = new URLSearchParams(location.search); if (params.get('google') === 'connected') setStatus('Google connected. Gmail and Calendar access are ready.'); else if (params.get('google') === 'error') setStatus(`Google authorization failed: ${params.get('reason') || 'please try again'}`) }, [location.search]); useEffect(() => { if (!session) return; (async () => { try { const [googleStatus, outlookStatus] = await Promise.all([ api<{ connected: boolean; reconnect_required?: boolean; message?: string }>('/integrations/google/status', session), api<{ connected: boolean }>('/integrations/outlook/status', session), ]); setGoogleConnected(googleStatus.connected); setGoogleReconnectRequired(Boolean(googleStatus.reconnect_required)); setOutlookConnected(outlookStatus.connected); if (googleStatus.reconnect_required) setStatus('Google access expired or was revoked. Reconnect Google below to resume Gmail and Calendar.'); } catch (e) { setStatus(e instanceof Error ? e.message : 'Unable to load connection status') } })(); }, [session.access_token, session.user.id]); const connectGoogle = async () => { try { const result = await api<{ authorization_url: string }>('/integrations/google/authorize', session); window.location.href = result.authorization_url } catch (e) { setStatus(e instanceof Error ? e.message : 'Unable to connect Google') } }; const connectOutlook = async () => { try { const result = await api<{ authorization_url: string }>('/integrations/outlook/authorize', session); setOutlookConnected(true); window.location.href = result.authorization_url } catch (e) { setStatus(e instanceof Error ? e.message : 'Unable to connect Outlook') } }; const googleLabel = googleConnected ? 'Reconnect' : googleReconnectRequired ? 'Reconnect Google' : 'Connect Google'; const googleState = googleConnected ? 'connected' : googleReconnectRequired ? 'reconnect required' : 'not connected'; return <><PageIntro kicker="Connected systems" title="Integrations." copy="Connect Gmail, Google Calendar, and Microsoft Outlook directly from your application workspace." />{status && <div className={status.startsWith('Google connected') ? 'sync-result' : 'error banner'}>{status}</div>}<div className="integration-grid"><Integration name="Gmail" status={googleState} action={connectGoogle} label={googleLabel} /><Integration name="Google Calendar" status={googleState} action={connectGoogle} label={googleLabel} /><Integration name="Microsoft Outlook" status={outlookConnected ? 'connected' : 'not connected'} action={connectOutlook} label={outlookConnected ? 'Reconnect' : 'Connect Outlook'} /></div></> }
function AuditPage() { return <><PageIntro kicker="Observability" title="Audit trail." copy="Every workflow action will be rendered from backend audit records as that API is added." /><Panel title="Append-only event trail" subtitle="Trigger, decisions, guardrails, approvals, actions"><Empty text="No audit events available from the backend." /></Panel></> }
function NotificationsPage() {
  const { session } = useOutletData()
  const [items, setItems] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => { if (!session) return; void api<Notification[]>('/portal/notifications', session).then(setItems).catch(e => setError(e instanceof Error ? e.message : 'Unable to load notifications')).finally(() => setLoading(false)) }, [session?.access_token, session?.user.id])
  return <><PageIntro kicker="Operations" title="Notifications." copy="Accepted reschedule approvals and workflow updates from your workspace." />{error && <div className="error banner">{error}</div>}<Panel title="Accepted approvals" subtitle="Meetings successfully approved and processed"><div className="notification-list">{loading ? <Loading /> : items.length ? items.map(item => <article className="notification-card" key={item.id}><span className="notification-icon">✓</span><div><b>{item.title}</b><p>{item.subject}</p><small>{item.sender || 'Candidate'} · {item.recorded_at ? formatSystemTimestamp(item.recorded_at) : 'Recently recorded'}</small></div><span className="badge approved">Accepted</span></article>) : <Empty text="No accepted approvals yet." />}</div></Panel></>
}
function SettingsPage() {
  const { session, data } = useOutletData()
  const [settings, setSettings] = useState<AutomationSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [workingDays, setWorkingDays] = useState<number[]>([0, 1, 2, 3, 4])
  const [shiftStart, setShiftStart] = useState('09:00')
  const [shiftEnd, setShiftEnd] = useState('17:00')

  useEffect(() => {
    if (!session) return
    void api<AutomationSettings>('/integrations/google/automation/settings', session)
      .then(result => {
        setSettings(result)
        setWorkingDays(result.working_days)
        setShiftStart(result.shift_start)
        setShiftEnd(result.shift_end)
      })
      .catch(error => setNotice(error instanceof Error ? error.message : 'Unable to load automation settings'))
  }, [session?.access_token, session?.user.id])

  const setAutomaticSuggestions = async (enabled: boolean) => {
    if (!session) return
    setSaving(true)
    setNotice('')
    try {
      const updated = await api<AutomationSettings>('/integrations/google/automation/settings', session, {
        method: 'PUT', body: JSON.stringify({ automatic_rescheduling_enabled: enabled }),
      })
      setSettings(updated)
      setNotice(enabled
        ? 'Automatic time suggestions are on. New requests will wait for your approval.'
        : 'Automatic time suggestions are off. Recruiters choose the proposed date and time.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Unable to save automation settings')
    } finally {
      setSaving(false)
    }
  }

  const saveWorkSchedule = async () => {
    if (!session) return
    setSaving(true)
    setNotice('')
    try {
      const updated = await api<AutomationSettings>('/integrations/google/automation/settings', session, {
        method: 'PUT', body: JSON.stringify({ working_days: workingDays, shift_start: shiftStart, shift_end: shiftEnd }),
      })
      setSettings(updated)
      setNotice('Working days and shift hours saved. Reschedule suggestions will use this schedule in your Google Calendar time zone.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Unable to save work schedule')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <PageIntro kicker="Configuration" title="Rescheduling settings." copy="Choose which days and hours the app should use when proposing an interview time." />
    {notice && <div className={notice.startsWith('Unable') ? 'error banner' : 'sync-result'}>{notice}</div>}
    <Panel title="Rescheduling assistance" subtitle="Calendar changes always wait for recruiter approval">
      {settings ? <div className="automation-setting">
        <div><b>Suggest available times automatically</b><p>{settings.automatic_rescheduling_enabled
          ? 'The app checks the candidate request and calendar, then places its suggested time in the Approval Queue. Nothing moves until a recruiter approves it.'
          : 'The Approval Queue asks the recruiter to choose a date and time. The app checks availability before approval.'}</p></div>
        <label className="toggle-control"><span>{settings.automatic_rescheduling_enabled ? 'On' : 'Off'}</span><input type="checkbox" checked={settings.automatic_rescheduling_enabled} disabled={saving} onChange={event => void setAutomaticSuggestions(event.target.checked)} /><i aria-hidden="true" /></label>
      </div> : <Loading />}
      <small className="setting-footnote">Inbox checks run every {settings?.sync_interval_seconds ?? '—'} seconds. Recruiter approval is required in both modes.</small>
    </Panel>
    <Panel title="Working days and shift" subtitle="Times use the connected Google Calendar time zone">
      <div className="schedule-settings">
        <div className="schedule-day-picker" role="group" aria-label="Working days">
          {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day, index) => {
            const selected = workingDays.includes(index)
            return <button type="button" key={day} className={selected ? 'schedule-day selected' : 'schedule-day'} aria-pressed={selected} disabled={saving || (selected && workingDays.length === 1)} onClick={() => setWorkingDays(current => selected ? current.filter(value => value !== index) : [...current, index].sort())}>{day}</button>
          })}
        </div>
        <div className="schedule-shift-fields">
          <label>Shift starts<input type="time" value={shiftStart} disabled={saving} onChange={event => setShiftStart(event.target.value)} /></label>
          <span>to</span>
          <label>Shift ends<input type="time" value={shiftEnd} disabled={saving} onChange={event => setShiftEnd(event.target.value)} /></label>
          <button className="primary" type="button" disabled={saving || workingDays.length === 0} onClick={() => void saveWorkSchedule()}>{saving ? 'Saving…' : 'Save schedule'}</button>
        </div>
      </div>
    </Panel>
    <Panel title="Workspace access" subtitle="Current authenticated account"><div className="settings"><div><span>Role</span><b>{data?.user.role ?? '—'}</b></div><div><span>Company</span><b>{data?.user.company_id ?? '—'}</b></div><div><span>Google connection</span><b>{data?.google_connected ? 'Connected' : 'Not connected'}</b></div></div></Panel>
  </>
}
function PageIntro({ kicker, title, copy }: { kicker: string; title: string; copy: string }) { return <div className="page-intro"><span className="eyebrow">{kicker}</span><h2>{title}</h2><p>{copy}</p></div> }
function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) { return <section className="card"><div className="card-head"><div><h3>{title}</h3><p>{subtitle}</p></div></div>{children}</section> }
function Kpi({ label, value, tone }: { label: string; value: string | number; tone: string }) { return <div className={`kpi ${tone}`}><span>{label}</span><strong>{value}</strong><small>From live database</small></div> }
function Workflow({ label, alt = false }: { label: string; alt?: boolean }) { return <div className="workflow-row"><span className={`workflow-mark ${alt ? 'alt' : ''}`}>✓</span><div><b>{label}</b><small>{alt ? 'Human decision boundary' : 'Backend automation path'}</small></div></div> }
function Integration({ name, status, action, label }: { name: string; status: string; action: () => void; label: string }) { return <section className="integration-card"><div className="integration-title"><span className="integration-logo">{name[0]}</span><div><h3>{name}</h3><p>OAuth 2.0 API</p></div></div><span className="badge">{status}</span><button className="secondary" onClick={action}>{label}</button></section> }
function Empty({ text }: { text: string }) { return <div className="empty"><span>◌</span>{text}</div> }
function Loading() { return <div className="loading">Loading live data…</div> }
function useOutletData() { const outlet = useOutletContext<{ session: Session; data: OverviewData | null; refresh: () => Promise<void> } | null>(); const saved = localStorage.getItem('recruiter-session'); const session = outlet?.session ?? (saved ? JSON.parse(saved) as Session : null); const data = outlet?.data ?? (session ? { user: session.user, metrics: { email_count: 0, reschedule_count: 0 }, google_connected: false } : null); return { session, data } }
export default App
