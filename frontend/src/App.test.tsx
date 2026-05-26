import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';

const clinicId = '11111111-1111-1111-1111-111111111111';

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(mockFetch));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('verifies OTP and loads the operations dashboard', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(/Clinic ID/i), clinicId);
    await user.type(screen.getByLabelText(/Owner WhatsApp/i), '+919000000001');
    await user.click(screen.getByRole('button', { name: /Send OTP/i }));
    await user.type(await screen.findByLabelText(/OTP/i), '123456');
    await user.click(screen.getByRole('button', { name: /Verify OTP/i }));

    expect(await screen.findByRole('heading', { name: /Demo Diagnostics/i })).toBeInTheDocument();
    expect(screen.getByText('Pending reports')).toBeInTheDocument();
    expect(screen.getByText('Failed messages')).toBeInTheDocument();
  });

  it('switches to failed messages and retries a row', async () => {
    const user = userEvent.setup();
    render(<App />);
    await login(user);

    await user.click(screen.getByRole('button', { name: /Failed/i }));
    await user.click(await screen.findByRole('button', { name: /Retry wamid.1/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        `/api/v1/clinics/${clinicId}/failed-messages/fail-1/retry`,
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  it('updates a booking status from the bookings table', async () => {
    const user = userEvent.setup();
    render(<App />);
    await login(user);

    await user.click(screen.getByRole('button', { name: /Bookings/i }));
    const statusFields = await screen.findAllByLabelText(/Status for CBC/i);
    await user.selectOptions(statusFields[0], 'report_ready');

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        `/api/v1/clinics/${clinicId}/test-bookings/booking-1`,
        expect.objectContaining({ method: 'PUT' }),
      );
    });
  });

  it('sends OTP request bodies accepted by the backend schema', async () => {
    const user = userEvent.setup();
    render(<App />);

    await login(user);

    const calls = vi.mocked(fetch).mock.calls;
    const sendRequest = calls.find(([input]) => String(input).endsWith('/auth/otp/send'));
    const verifyRequest = calls.find(([input]) => String(input).endsWith('/auth/otp/verify'));

    expect(JSON.parse(String(sendRequest?.[1]?.body))).toEqual({
      owner_whatsapp: '+919000000001',
    });
    expect(JSON.parse(String(verifyRequest?.[1]?.body))).toEqual({
      owner_whatsapp: '+919000000001',
      otp: '123456',
    });
  });

  it('normalizes local owner WhatsApp input before sending OTP', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(/Clinic ID/i), clinicId);
    await user.type(screen.getByLabelText(/Owner WhatsApp/i), '9000000001');
    await user.click(screen.getByRole('button', { name: /Send OTP/i }));

    const calls = vi.mocked(fetch).mock.calls;
    const sendRequest = calls.find(([input]) => String(input).endsWith('/auth/otp/send'));

    expect(JSON.parse(String(sendRequest?.[1]?.body))).toEqual({
      owner_whatsapp: '+919000000001',
    });
  });
});

async function login(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Clinic ID/i), clinicId);
  await user.type(screen.getByLabelText(/Owner WhatsApp/i), '+919000000001');
  await user.click(screen.getByRole('button', { name: /Send OTP/i }));
  await user.type(await screen.findByLabelText(/OTP/i), '123456');
  await user.click(screen.getByRole('button', { name: /Verify OTP/i }));
  await screen.findByRole('heading', { name: /Demo Diagnostics/i });
}

async function mockFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (url.endsWith('/auth/otp/send')) return json({ data: { sent: true } });
  if (url.endsWith('/auth/otp/verify')) return json({ data: { access_token: 'token' } });
  if (url.endsWith(`/clinics/${clinicId}`)) {
    return json({
      data: {
        name: 'Demo Diagnostics',
        owner_name: 'Owner',
        whatsapp_number: '+918100000001',
        owner_whatsapp: '+919000000001',
        address: '1 Main Road',
        city: 'Bhopal',
        pincode: '462001',
        timezone: 'Asia/Kolkata',
        plan: 'diagnostic',
        plan_active: true,
        settings: {},
      },
    });
  }
  if (url.includes('/test-bookings?status=sample_collected')) {
    return json({ data: [] });
  }
  if (url.includes('/test-bookings?status=processing')) {
    return json({ data: [booking('booking-1', 'processing')] });
  }
  if (url.includes('/test-bookings?status=report_ready')) {
    return json({ data: [] });
  }
  if (url.endsWith('/test-bookings')) {
    return json({ data: [booking('booking-1', 'processing'), booking('booking-2', 'delivered')] });
  }
  if (url.endsWith('/test-bookings/booking-1')) {
    return json({ data: booking('booking-1', 'report_ready') });
  }
  if (url.endsWith('/patients')) {
    return json({ data: [{ id: 'patient-1', name: 'Asha', whatsapp_number: '+9177', tags: [], notes: null }] });
  }
  if (url.includes('/tests?active=true')) {
    return json({ data: [{ id: 'test-1', name: 'CBC', price: '300.00', category: 'Blood', is_active: true }] });
  }
  if (url.endsWith('/failed-messages')) {
    return json({
      data: [{ id: 'fail-1', whatsapp_number: '+9177', wa_message_id: 'wamid.1', error: 'Flow crashed', retry_count: 0 }],
    });
  }
  if (url.endsWith('/failed-messages/fail-1/retry')) {
    return json({ data: { id: 'fail-1', resolved: true } });
  }
  return json({});
}

function booking(id: string, status: string) {
  return {
    id,
    patient_name: 'Asha',
    patient_id: 'patient-1',
    patient_whatsapp: '+9177',
    test_id: 'test-1',
    test_name: 'CBC',
    booking_type: 'walkin',
    status,
    amount: '300.00',
    payment_status: 'paid',
    collection_slot: null,
    report_file_path: null,
    booked_at: '2026-05-23T09:00:00+05:30',
    notes: null,
  };
}

function json(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
}
