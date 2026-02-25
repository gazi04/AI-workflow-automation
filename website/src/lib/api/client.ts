import { env } from '$env/dynamic/public';

export const BASE_URL = env.PUBLIC_API_URL || 'http://localhost:8000';

let refreshPromise: Promise<string | null> | null = null;

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
	const url = `${BASE_URL}${endpoint}`;

	const headers = {
		'Content-Type': 'application/json',
		...options.headers
	};

	const fetcher =
		typeof window !== 'undefined' && localStorage.getItem('access_token') ? authorizedFetch : fetch;

	let response = await fetcher(url, { ...options, headers });

	if (response.status === 401) {
		if (!refreshPromise) {
			refreshPromise = attemptTokenRefresh().finally(() => {
				refreshPromise = null;
			});
		}

		try {
			const newToken = await refreshPromise;
			if (newToken) {
				const retryHeaders = {
					...headers,
					Authorization: `Bearer ${newToken}`
				};
				response = await fetch(url, { ...options, headers: retryHeaders });
			} else {
				handleLogout();
				throw { status: 401, message: 'Session expired' };
			}
		} catch (err) {
			handleLogout();
			throw { status: 401, message: 'Session expired' };
		}
	}

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}));
		throw { status: response.status, ...errorData };
	}

	return response.json();
}

async function attemptTokenRefresh(): Promise<string | null> {
	const refreshToken = localStorage.getItem('refresh_token');
	if (!refreshToken) return null;

	try {
		const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ refresh_token: refreshToken })
		});

		if (res.ok) {
			const data = await res.json();

			if (data.access_token) {
				localStorage.setItem('access_token', data.access_token);

				if (data.refresh_token) {
					localStorage.setItem('refresh_token', data.refresh_token);
				}

				return data.access_token;
			}
		}
	} catch (err) {
		console.error('Token refresh network error:', err);
	}

	return null;
}

async function authorizedFetch(url: string, options: RequestInit = {}) {
	const token = localStorage.getItem('access_token');
	const headers = {
		...options.headers,
		Authorization: `Bearer ${token}`
	};
	return fetch(url, { ...options, headers });
}

function handleLogout() {
	if (typeof window !== 'undefined') {
		localStorage.clear();
		window.location.href = '/login?error=session_expired';
	}
}

export const api = {
	get: <T>(url: string) => request<T>(url, { method: 'GET' }),
	post: <T>(url: string, body: any) =>
		request<T>(url, { method: 'POST', body: JSON.stringify(body) }),
	patch: <T>(url: string, body: any) =>
		request<T>(url, { method: 'PATCH', body: JSON.stringify(body) }),
	delete: <T>(url: string) => request<T>(url, { method: 'DELETE' })
};
