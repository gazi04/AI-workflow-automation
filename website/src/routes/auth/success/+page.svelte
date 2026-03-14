<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Loader } from 'lucide-svelte';

	onMount(() => {
		const accessToken = $derived(page.url.searchParams.get('access_token'));
		const refreshToken = $derived(page.url.searchParams.get('refreshToken'));

		if (accessToken && refreshToken) {
			localStorage.setItem('access_token', accessToken);
			localStorage.setItem('refresh_token', refreshToken);

			goto('/dashboard');
		} else {
			goto('/login?error=token_delivery_failed');
		}
	});
</script>

<div class="flex min-h-screen items-center justify-center">
	<div class="flex flex-col items-center gap-2">
		<Loader class="h-8 w-8 animate-spin text-primary" />
		<p class="text-sm text-muted-foreground">Finalizing your session...</p>
	</div>
</div>
