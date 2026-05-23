import {
  AlertTriangle,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  LogIn,
  RotateCcw,
  Search,
  Settings,
  Upload,
  Users,
} from 'lucide-react';
import { FormEvent, useMemo, useState } from 'react';

type TabId = 'overview' | 'bookings' | 'reports' | 'failed' | 'patients' | 'tests' | 'settings';

type ApiState = {
  clinicId: string;
  token: string;
};

type Booking = {
  id: string;
  patient_id: string;
  patient_name: string | null;
  patient_whatsapp: string;
  test_id: string | null;
  test_name: string;
  booking_type: string;
  status: string;
  amount: string | null;
  payment_status: string;
  collection_slot: string | null;
  report_file_path: string | null;
  booked_at: string;
  notes: string | null;
};

type Patient = {
  id: string;
  name: string | null;
  whatsapp_number: string;
  tags: string[];
  notes: string | null;
};

type TestItem = {
  id: string;
  name: string;
  price: string | null;
  category: string | null;
  is_active: boolean;
};

type FailedMessage = {
  id: string;
  whatsapp_number: string | null;
  wa_message_id: string | null;
  error: string | null;
  retry_count: number;
};

type ClinicSettings = {
  id: string;
  name: string;
  owner_name: string | null;
  whatsapp_number: string;
  owner_whatsapp: string;
  address: string | null;
  city: string | null;
  pincode: string | null;
  timezone: string;
  plan: string;
  plan_active: boolean;
  settings: Record<string, unknown>;
};

type DashboardData = {
  clinic: ClinicSettings | null;
  bookings: Booking[];
  pendingReports: Booking[];
  patients: Patient[];
  tests: TestItem[];
  failedMessages: FailedMessage[];
};

type ApiRequestInit = Omit<RequestInit, 'body'> & {
  body?: BodyInit | Record<string, unknown> | null;
};

const emptyData: DashboardData = {
  clinic: null,
  bookings: [],
  pendingReports: [],
  patients: [],
  tests: [],
  failedMessages: [],
};

const tabs: Array<{ id: TabId; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'bookings', label: 'Bookings', icon: ListChecks },
  { id: 'reports', label: 'Reports', icon: Upload },
  { id: 'failed', label: 'Failed', icon: AlertTriangle },
  { id: 'patients', label: 'Patients', icon: Users },
  { id: 'tests', label: 'Catalog', icon: FlaskConical },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export function App() {
  const [apiState, setApiState] = useState<ApiState | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [data, setData] = useState<DashboardData>(emptyData);
  const [notice, setNotice] = useState('Enter the owner OTP to open the dashboard.');

  async function handleVerified(nextState: ApiState) {
    setApiState(nextState);
    setNotice('Loading dashboard...');
    const nextData = await loadDashboard(nextState);
    setData(nextData);
    setNotice('Dashboard ready.');
  }

  async function retryFailedMessage(messageId: string) {
    if (!apiState) return;
    await apiFetch(apiState, `/clinics/${apiState.clinicId}/failed-messages/${messageId}/retry`, {
      method: 'POST',
    });
    setData(await loadDashboard(apiState));
    setNotice('Failed message retried.');
  }

  async function updateBookingStatus(bookingId: string, status: string) {
    if (!apiState) return;
    await apiFetch(apiState, `/clinics/${apiState.clinicId}/test-bookings/${bookingId}`, {
      method: 'PUT',
      body: { status },
    });
    setData(await loadDashboard(apiState));
    setNotice('Booking status updated.');
  }

  async function uploadReport(bookingId: string, file: File) {
    if (!apiState) return;
    const body = new FormData();
    body.append('report_pdf', file);
    await apiFetch(apiState, `/clinics/${apiState.clinicId}/test-bookings/${bookingId}/report-upload`, {
      method: 'POST',
      body,
    });
    setData(await loadDashboard(apiState));
    setNotice('Report uploaded and sent.');
  }

  async function updateClinicSettings(payload: Partial<ClinicSettings>) {
    if (!apiState) return;
    const response = await apiFetch<{ data: ClinicSettings }>(apiState, `/clinics/${apiState.clinicId}`, {
      method: 'PUT',
      body: payload,
    });
    setData((current) => ({ ...current, clinic: response.data }));
    setNotice('Settings saved.');
  }

  if (!apiState) {
    return <LoginScreen onVerified={handleVerified} notice={notice} setNotice={setNotice} />;
  }

  return (
    <main className="min-h-screen bg-[#f7faf8] text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Winzapp</p>
            <h1 className="text-xl font-semibold">{data.clinic?.name ?? 'Clinic dashboard'}</h1>
          </div>
          <div className="text-right text-sm text-slate-600">
            <p>{data.clinic?.whatsapp_number}</p>
            <p>{notice}</p>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-5 px-5 py-5 lg:grid-cols-[220px_1fr]">
        <nav className="flex gap-2 overflow-x-auto border-b border-line pb-3 lg:block lg:border-b-0 lg:pb-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={`focus-ring flex min-w-fit items-center gap-2 rounded-md px-3 py-2 text-sm transition ${
                  activeTab === tab.id ? 'bg-teal text-white' : 'text-slate-700 hover:bg-mist'
                }`}
                onClick={() => setActiveTab(tab.id)}
                type="button"
              >
                <Icon size={16} />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <section className="min-w-0">
          {activeTab === 'overview' && <Overview data={data} />}
          {activeTab === 'bookings' && (
            <BookingsTable bookings={data.bookings} onStatusChange={updateBookingStatus} />
          )}
          {activeTab === 'reports' && (
            <ReportsTable bookings={data.pendingReports} onUpload={uploadReport} />
          )}
          {activeTab === 'failed' && (
            <FailedMessagesTable messages={data.failedMessages} onRetry={retryFailedMessage} />
          )}
          {activeTab === 'patients' && <PatientsTable patients={data.patients} />}
          {activeTab === 'tests' && <TestsTable tests={data.tests} />}
          {activeTab === 'settings' && (
            <SettingsView clinic={data.clinic} onSave={updateClinicSettings} />
          )}
        </section>
      </div>
    </main>
  );
}

function LoginScreen({
  onVerified,
  notice,
  setNotice,
}: {
  onVerified: (state: ApiState) => Promise<void>;
  notice: string;
  setNotice: (notice: string) => void;
}) {
  const [clinicId, setClinicId] = useState('');
  const [ownerWhatsapp, setOwnerWhatsapp] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);

  async function sendOtp(event: FormEvent) {
    event.preventDefault();
    await publicFetch('/auth/otp/send', { method: 'POST', body: { clinic_id: clinicId, owner_whatsapp: ownerWhatsapp } });
    setOtpSent(true);
    setNotice('OTP sent on WhatsApp.');
  }

  async function verifyOtp(event: FormEvent) {
    event.preventDefault();
    const response = await publicFetch<{ data: { access_token: string } }>('/auth/otp/verify', {
      method: 'POST',
      body: { clinic_id: clinicId, owner_whatsapp: ownerWhatsapp, otp },
    });
    await onVerified({ clinicId, token: response.data.access_token });
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f7faf8] px-5 text-ink">
      <section className="w-full max-w-md border border-line bg-white p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Winzapp</p>
        <h1 className="mt-2 text-2xl font-semibold">Owner login</h1>
        <p className="mt-2 text-sm text-slate-600">{notice}</p>

        <form className="mt-6 space-y-4" onSubmit={otpSent ? verifyOtp : sendOtp}>
          <label className="block text-sm font-medium">
            Clinic ID
            <input
              className="focus-ring mt-1 w-full border border-line px-3 py-2"
              onChange={(event) => setClinicId(event.target.value)}
              required
              value={clinicId}
            />
          </label>
          <label className="block text-sm font-medium">
            Owner WhatsApp
            <input
              className="focus-ring mt-1 w-full border border-line px-3 py-2"
              onChange={(event) => setOwnerWhatsapp(event.target.value)}
              required
              value={ownerWhatsapp}
            />
          </label>
          {otpSent && (
            <label className="block text-sm font-medium">
              OTP
              <input
                className="focus-ring mt-1 w-full border border-line px-3 py-2"
                onChange={(event) => setOtp(event.target.value)}
                required
                value={otp}
              />
            </label>
          )}
          <button
            className="focus-ring flex w-full items-center justify-center gap-2 rounded-md bg-teal px-4 py-2 font-medium text-white"
            type="submit"
          >
            <LogIn size={17} />
            {otpSent ? 'Verify OTP' : 'Send OTP'}
          </button>
        </form>
      </section>
    </main>
  );
}

function Overview({ data }: { data: DashboardData }) {
  const stats = useMemo(
    () => [
      ['Bookings', data.bookings.length],
      ['Pending reports', data.pendingReports.length],
      ['Failed messages', data.failedMessages.length],
      ['Active tests', data.tests.filter((test) => test.is_active).length],
    ],
    [data],
  );
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-px overflow-hidden border border-line bg-line md:grid-cols-4">
        {stats.map(([label, value]) => (
          <div className="bg-white p-4" key={label}>
            <p className="text-sm text-slate-600">{label}</p>
            <p className="mt-2 text-3xl font-semibold">{value}</p>
          </div>
        ))}
      </div>
      <div className="border border-line bg-white p-4">
        <h2 className="font-semibold">Operations queue</h2>
        <p className="mt-2 text-sm text-slate-600">
          Review pending reports first, then failed messages, then catalog updates.
        </p>
      </div>
    </div>
  );
}

function BookingsTable({
  bookings,
  onStatusChange,
}: {
  bookings: Booking[];
  onStatusChange: (bookingId: string, status: string) => void;
}) {
  return (
    <TableShell title="Test bookings">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2 pr-4">Patient</th>
              <th className="py-2 pr-4">Test</th>
              <th className="py-2 pr-4">Type</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Payment</th>
              <th className="py-2 pr-4">Booked</th>
            </tr>
          </thead>
          <tbody>
            {bookings.map((booking) => (
              <tr className="border-b border-line" key={booking.id}>
                <td className="py-3 pr-4">{booking.patient_name ?? booking.patient_whatsapp}</td>
                <td className="py-3 pr-4">{booking.test_name}</td>
                <td className="py-3 pr-4">{formatCell(booking.booking_type)}</td>
                <td className="py-3 pr-4">
                  <select
                    aria-label={`Status for ${booking.test_name}`}
                    className="focus-ring w-44 border border-line bg-white px-2 py-1"
                    onChange={(event) => onStatusChange(booking.id, event.target.value)}
                    value={booking.status}
                  >
                    {bookingStatuses.map((status) => (
                      <option key={status} value={status}>
                        {status.replaceAll('_', ' ')}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-3 pr-4">{formatCell(booking.payment_status)}</td>
                <td className="py-3 pr-4">{formatDate(booking.booked_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TableShell>
  );
}

function ReportsTable({ bookings, onUpload }: { bookings: Booking[]; onUpload: (bookingId: string, file: File) => void }) {
  return (
    <TableShell title="Pending reports">
      {bookings.map((booking) => (
        <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line py-3" key={booking.id}>
          <div>
            <p className="font-medium">{booking.test_name}</p>
            <p className="text-sm text-slate-600">{booking.patient_name ?? booking.patient_whatsapp}</p>
          </div>
          <label className="focus-within:ring-2 focus-within:ring-teal">
            <span className="flex cursor-pointer items-center gap-2 rounded-md bg-teal px-3 py-2 text-sm text-white">
              <Upload size={15} /> Upload
            </span>
            <input
              accept="application/pdf"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onUpload(booking.id, file);
              }}
              type="file"
            />
          </label>
        </div>
      ))}
    </TableShell>
  );
}

function FailedMessagesTable({ messages, onRetry }: { messages: FailedMessage[]; onRetry: (messageId: string) => void }) {
  return (
    <TableShell title="Failed messages">
      {messages.map((message) => (
        <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-b border-line py-3" key={message.id}>
          <div>
            <p className="font-medium">{message.wa_message_id ?? message.id}</p>
            <p className="text-sm text-slate-600">{message.error}</p>
          </div>
          <button
            aria-label={`Retry ${message.wa_message_id ?? message.id}`}
            className="focus-ring rounded-md border border-line px-3 py-2"
            onClick={() => onRetry(message.id)}
            type="button"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      ))}
    </TableShell>
  );
}

function PatientsTable({ patients }: { patients: Patient[] }) {
  return <DataTable title="Patients" rows={patients} columns={['name', 'whatsapp_number', 'tags', 'notes']} />;
}

function TestsTable({ tests }: { tests: TestItem[] }) {
  return <DataTable title="Test catalog" rows={tests} columns={['name', 'category', 'price', 'is_active']} />;
}

function SettingsView({
  clinic,
  onSave,
}: {
  clinic: ClinicSettings | null;
  onSave: (payload: Partial<ClinicSettings>) => void;
}) {
  const [form, setForm] = useState({
    name: clinic?.name ?? '',
    owner_name: clinic?.owner_name ?? '',
    address: clinic?.address ?? '',
    city: clinic?.city ?? '',
    pincode: clinic?.pincode ?? '',
    timezone: clinic?.timezone ?? 'Asia/Kolkata',
  });

  if (!clinic) {
    return <TableShell title="Settings">Clinic settings are not loaded.</TableShell>;
  }

  function updateField(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({
      name: form.name,
      owner_name: form.owner_name || null,
      address: form.address || null,
      city: form.city || null,
      pincode: form.pincode || null,
      timezone: form.timezone,
    });
  }

  return (
    <TableShell title="Settings">
      <form className="grid gap-4 text-sm md:grid-cols-2" onSubmit={submit}>
        <label className="block font-medium">
          Clinic
          <input
            className="focus-ring mt-1 w-full border border-line px-3 py-2"
            onChange={(event) => updateField('name', event.target.value)}
            value={form.name}
          />
        </label>
        <label className="block font-medium">
          Owner
          <input
            className="focus-ring mt-1 w-full border border-line px-3 py-2"
            onChange={(event) => updateField('owner_name', event.target.value)}
            value={form.owner_name}
          />
        </label>
        <label className="block font-medium md:col-span-2">
          Address
          <input
            className="focus-ring mt-1 w-full border border-line px-3 py-2"
            onChange={(event) => updateField('address', event.target.value)}
            value={form.address}
          />
        </label>
        <label className="block font-medium">
          City
          <input
            className="focus-ring mt-1 w-full border border-line px-3 py-2"
            onChange={(event) => updateField('city', event.target.value)}
            value={form.city}
          />
        </label>
        <label className="block font-medium">
          Pincode
          <input
            className="focus-ring mt-1 w-full border border-line px-3 py-2"
            onChange={(event) => updateField('pincode', event.target.value)}
            value={form.pincode}
          />
        </label>
        <label className="block font-medium">
          Timezone
          <input
            className="focus-ring mt-1 w-full border border-line px-3 py-2"
            onChange={(event) => updateField('timezone', event.target.value)}
            value={form.timezone}
          />
        </label>
        <div className="grid content-end gap-1 text-slate-600">
          <span>Plan: {clinic.plan}</span>
          <span>WhatsApp: {clinic.whatsapp_number}</span>
        </div>
        <button className="focus-ring rounded-md bg-teal px-4 py-2 font-medium text-white md:w-fit" type="submit">
          Save settings
        </button>
      </form>
    </TableShell>
  );
}

function DataTable<T extends Record<string, unknown>>({ title, rows, columns }: { title: string; rows: T[]; columns: string[] }) {
  return (
    <TableShell title={title}>
      <div className="mb-3 flex items-center gap-2 border border-line px-3 py-2 text-sm text-slate-500">
        <Search size={15} />
        <span>Search and filters arrive in the next dashboard polish pass.</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line text-xs uppercase text-slate-500">
            <tr>{columns.map((column) => <th className="py-2 pr-4" key={column}>{column.replaceAll('_', ' ')}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr className="border-b border-line" key={String(row.id ?? index)}>
                {columns.map((column) => <td className="py-3 pr-4" key={column}>{formatCell(row[column])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TableShell>
  );
}

function TableShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-line bg-white p-4">
      <h2 className="mb-4 font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function formatCell(value: unknown) {
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
}

function formatDate(value: string | null) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

const bookingStatuses = [
  'booked',
  'sample_collected',
  'processing',
  'report_ready',
  'delivered',
  'cancelled',
];

const pendingReportStatuses = ['sample_collected', 'processing', 'report_ready'];

async function loadDashboard(state: ApiState): Promise<DashboardData> {
  const [clinic, bookings, pendingReports, patients, tests, failedMessages] = await Promise.all([
    apiFetch<{ data: ClinicSettings }>(state, `/clinics/${state.clinicId}`),
    apiFetch<{ data: Booking[] }>(state, `/clinics/${state.clinicId}/test-bookings`),
    fetchPendingReports(state),
    apiFetch<{ data: Patient[] }>(state, `/clinics/${state.clinicId}/patients`),
    apiFetch<{ data: TestItem[] }>(state, `/clinics/${state.clinicId}/tests?active=true`),
    apiFetch<{ data: FailedMessage[] }>(state, `/clinics/${state.clinicId}/failed-messages`),
  ]);
  return {
    clinic: clinic.data,
    bookings: bookings.data,
    pendingReports: pendingReports.data,
    patients: patients.data,
    tests: tests.data,
    failedMessages: failedMessages.data,
  };
}

async function fetchPendingReports(state: ApiState): Promise<{ data: Booking[] }> {
  const results = await Promise.all(
    pendingReportStatuses.map((status) =>
      apiFetch<{ data: Booking[] }>(state, `/clinics/${state.clinicId}/test-bookings?status=${status}`),
    ),
  );
  return { data: results.flatMap((result) => result.data) };
}

async function apiFetch<T>(state: ApiState, path: string, init: ApiRequestInit = {}): Promise<T> {
  return publicFetch<T>(path, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${state.token}`,
    },
  });
}

async function publicFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  let body = init.body as BodyInit | null | undefined;
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(init.body);
  }
  const response = await fetch(`/api/v1${path}`, { ...init, headers, body });
  if (!response.ok) throw new Error(`Request failed with ${response.status}`);
  return (await response.json()) as T;
}
