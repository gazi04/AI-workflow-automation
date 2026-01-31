<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { Loader2 } from 'lucide-svelte';

	onMount(() => {
		// 1. Get the tokens from the URL query parameters
		const accessToken = $page.url.searchParams.get('access_token');
		const refreshToken = $page.url.searchParams.get('refresh_token');

		if (accessToken && refreshToken) {
			// 2. Save them exactly where your app expects them
			localStorage.setItem('access_token', accessToken);
			localStorage.setItem('refresh_token', refreshToken);

			// 3. Success! Clear the URL and go to dashboard
			goto('/dashboard');
		} else {
			// Handle error if tokens are missing
			goto('/login?error=token_delivery_failed');
		}
	});
</script>

<div class="flex min-h-screen items-center justify-center">
	<div class="flex flex-col items-center gap-2">
		<Loader2 class="h-8 w-8 animate-spin text-primary" />
		<p class="text-sm text-muted-foreground">Finalizing your session...</p>
	</div>
</div>
