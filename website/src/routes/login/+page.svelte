<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';
	import { Chrome, Loader2, AlertCircle } from 'lucide-svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	const API_BASE_URL = 'http://backend:8000';
	let isLoading = $state(false);

	// Reactively derive the error message from the URL search params
	const errorMessage = $derived($page.url.searchParams.get('error'));

	async function handleGoogleLogin() {
		isLoading = true;
		try {
			const response = await fetch(`${API_BASE_URL}/api/auth/connect/google`);
			if (!response.ok) throw new Error('Failed to fetch auth URL');

			const data = await response.json();

			if (data.auth_url) {
				window.location.href = data.auth_url;
			} else {
				console.error('No auth_url found in response', data);
			}
		} catch (error) {
			console.error('Login error:', error);
			// If the initial fetch fails, we set a local error state
			goto('/login?error=connection_failed');
		} finally {
			isLoading = false;
		}
	}
</script>

<div class="flex min-h-screen flex-col items-center justify-center bg-muted/50 p-4">
	<Card.Root class="w-full max-w-md">
		<Card.Header class="text-center">
			<Card.Title class="text-2xl font-semibold">Welcome back</Card.Title>
			<Card.Description>Login to manage your AI email automations</Card.Description>
		</Card.Header>

		<Card.Content class="flex flex-col items-center justify-center py-6">
			{#if errorMessage}
				<div
					class="mb-6 flex w-full animate-in items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive zoom-in-95 fade-in"
				>
					<AlertCircle class="h-4 w-4" />
					<p class="font-medium">
						{#if errorMessage === 'auth_failed'}
							Authentication failed. Google connection was reset.
						{:else if errorMessage === 'connection_failed'}
							Could not reach the server.
						{:else}
							An unexpected error occurred. Please try again.
						{/if}
					</p>
				</div>
			{/if}

			<div class="rounded-full bg-primary/10 p-4">
				<Chrome class="h-8 w-8 text-primary" />
			</div>
		</Card.Content>

		<Card.Footer>
			<Button variant="outline" class="w-full" onclick={handleGoogleLogin} disabled={isLoading}>
				{#if isLoading}
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
					Connecting...
				{:else}
					<Chrome class="mr-2 h-4 w-4" />
					Sign in with Google
				{/if}
			</Button>
		</Card.Footer>
	</Card.Root>

	<p class="mt-4 max-w-[280px] text-center text-xs text-muted-foreground">
		By signing in, you grant the agent permission to manage selected Gmail drafts and labels.
	</p>
</div>
