import { env } from '$env/dynamic/public';

const BASE_URL = env.PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
	const url = `${BASE_URL}${endpoint}`;

	const headers = {
		'Content-Type': 'application/json',
		...options.headers
	};

	const fetcher = localStorage.getItem('access_token') ? authorizedFetch : fetch;

	const response = await fetcher(url, { ...options, headers });

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}));
		throw { status: response.status, ...errorData };
	}

	return response.json();
}

export const api = {
	get: <T>(url: string) => request<T>(url, { method: 'GET' }),
	post: <T>(url: string, body: any) => request<T>(url, { method: 'POST', body: JSON.stringify(body) }),
	patch: <T>(url: string, body: any) => request<T>(url, { method: 'PATCH', body: JSON.stringify(body) }),
	delete: <T>(url: string) => request<T>(url, { method: 'DELETE' })
};

async function authorizedFetch(url: string, options: RequestInit = {}) {
	const token = localStorage.getItem('access_token');

	const headers = {
		...options.headers,
		Authorization: `Bearer ${token}`,
		'Content-Type': 'application/json'
	};

	const response = await fetch(url, { ...options, headers });

	if (response.status === 401) {
		localStorage.clear();
		window.location.href = '/login';
	}

	return response;
}
