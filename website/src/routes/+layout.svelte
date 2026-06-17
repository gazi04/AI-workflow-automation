<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	let { children } = $props();

	onMount(() => {
		const publicRoutes = ['/login', '/auth/success'];

		const isPublicRoute = publicRoutes.some((route) => page.url.pathname.startsWith(route));
		// Auth tokens are HttpOnly cookies; use the readable csrf_token cookie as a
		// client-side "logged in" hint. The server still enforces real auth.
		const hasSession = /(?:^|;\s*)csrf_token=/.test(document.cookie);

		if (!hasSession && !isPublicRoute) {
			goto('/login');
		}

		if (hasSession && page.url.pathname === '/login') {
			goto('/dashboard');
		}
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
{@render children()}
