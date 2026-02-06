<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	let { children } = $props();

	onMount(() => {
		const publicRoutes = ['/login', '/auth/success'];

		const isPublicRoute = publicRoutes.some((route) => $page.url.pathname.startsWith(route));
		const token = localStorage.getItem('access_token');

		if (!token && !isPublicRoute) {
			goto('/login');
		}

		if (token && $page.url.pathname === '/login') {
			goto('/dashboard');
		}
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
{@render children()}
