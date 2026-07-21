import { env } from '$env/dynamic/public';

export const BASE_URL = env.PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Build a WebSocket URL against the same origin as the REST API, so both follow
 * PUBLIC_API_URL. Replacing the leading `http` maps http:// -> ws:// and
 * https:// -> wss://.
 */
export function wsUrl(path: string): string {
	return `${BASE_URL.replace(/^http/, 'ws')}${path}`;
}

let refreshPromise: Promise<boolean> | null = null;

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function getCsrfToken(): string | null {
	if (typeof document === 'undefined') return null;
	const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
	return match ? decodeURIComponent(match[1]) : null;
}

function buildHeaders(method: string, extra: HeadersInit = {}): HeadersInit {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(extra as Record<string, string>)
	};
	if (MUTATING_METHODS.has(method.toUpperCase())) {
		const csrf = getCsrfToken();
		if (csrf) headers['X-CSRF-Token'] = csrf;
	}
	return headers;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
	const url = `${BASE_URL}${endpoint}`;
	const method = options.method || 'GET';
	const headers = buildHeaders(method, options.headers);

	let response = await fetch(url, { ...options, headers, credentials: 'include' });

	if (response.status === 401) {
		if (!refreshPromise) {
			refreshPromise = attemptTokenRefresh().finally(() => {
				refreshPromise = null;
			});
		}

		try {
			const refreshed = await refreshPromise;
			if (refreshed) {
				// Cookies are refreshed; rebuild headers to pick up the new CSRF token.
				response = await fetch(url, {
					...options,
					headers: buildHeaders(method, options.headers),
					credentials: 'include'
				});
			} else {
				await handleLogout();
				throw { status: 401, message: 'Session expired' };
			}
		} catch (err) {
			await handleLogout();
			throw { status: 401, message: 'Session expired' };
		}
	}

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}));
		throw { status: response.status, ...errorData };
	}

	return response.json();
}

async function attemptTokenRefresh(): Promise<boolean> {
	try {
		const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
			method: 'POST',
			headers: buildHeaders('POST'),
			credentials: 'include'
		});
		return res.ok;
	} catch (err) {
		console.error('Token refresh network error:', err);
		return false;
	}
}

async function handleLogout() {
	if (typeof window === 'undefined') return;
	try {
		await fetch(`${BASE_URL}/api/auth/logout`, {
			method: 'POST',
			headers: buildHeaders('POST'),
			credentials: 'include'
		});
	} catch {
		// ignore network errors on logout
	}
	window.location.href = '/login?error=session_expired';
}

export const api = {
	get: <T>(url: string) => request<T>(url, { method: 'GET' }),
	post: <T>(url: string, body: any) =>
		request<T>(url, { method: 'POST', body: JSON.stringify(body) }),
	patch: <T>(url: string, body: any) =>
		request<T>(url, { method: 'PATCH', body: JSON.stringify(body) }),
	delete: <T>(url: string) => request<T>(url, { method: 'DELETE' })
};
