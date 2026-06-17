<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Loader } from 'lucide-svelte';

	onMount(async () => {
		const code = page.url.searchParams.get('code');
		if (!code) {
			goto('/login?error=token_delivery_failed');
			return;
		}
		try {
			const res = await fetch(`/api/auth/exchange?code=${encodeURIComponent(code)}`);
			if (!res.ok) throw new Error('exchange failed');
			const { access_token, refresh_token } = await res.json();
			localStorage.setItem('access_token', access_token);
			localStorage.setItem('refresh_token', refresh_token);
			goto('/dashboard');
		} catch {
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
