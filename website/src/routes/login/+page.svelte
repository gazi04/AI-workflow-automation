<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import * as Card from "$lib/components/ui/card";
	import { Chrome, Loader2 } from "lucide-svelte";

	const API_BASE_URL = "http://localhost:8000"; 
	let isLoading = $state(false); // Using Svelte 5 runes if applicable, or 'let' for Svelte 4

	async function handleGoogleLogin() {
		isLoading = true;
		try {
			// 1. Consume the API endpoint
			const response = await fetch(`${API_BASE_URL}/api/auth/connect/google`);
			
			if (!response.ok) throw new Error("Failed to fetch auth URL");
			
			const data = await response.json();
			
			// 2. Open the returned auth_url
			if (data.auth_url) {
				window.location.href = data.auth_url;
			} else {
				console.error("No auth_url found in response", data);
			}
		} catch (error) {
			console.error("Login error:", error);
		} finally {
			isLoading = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-muted/50 p-4">
	<Card.Root class="w-full max-w-md">
		<Card.Header class="text-center">
			<Card.Title class="text-2xl font-semibold">Welcome back</Card.Title>
			<Card.Description>
				Login to manage your AI email automations
			</Card.Description>
		</Card.Header>
		
		<Card.Content class="flex flex-col items-center justify-center py-6">
			<div class="rounded-full bg-primary/10 p-4">
				<Chrome class="h-8 w-8 text-primary" />
			</div>
		</Card.Content>

		<Card.Footer>
			<Button 
				variant="outline" 
				class="w-full" 
				onclick={handleGoogleLogin} 
				disabled={isLoading}
			>
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
</div>
