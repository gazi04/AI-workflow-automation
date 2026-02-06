import { redirect, type Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
	const path = event.url.pathname;

	if (path === '/') {
		throw redirect(307, '/dashboard');
	}

	const response = await resolve(event);
	return response;
};
