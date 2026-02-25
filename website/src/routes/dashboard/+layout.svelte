<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { LayoutDashboard, PlusCircle, Plug } from 'lucide-svelte';

	let { children } = $props();

	let gmailNeedsReconnect = $state(false);

	type IntegrationStatus = {
		provider: string;
		is_connected: boolean;
		email: string | null;
		needs_reconnect: boolean;
	};

	type ConnectionStatusResponse = {
		integrations: IntegrationStatus[];
	};

	function triggerReconnectAlert() {
		gmailNeedsReconnect = true;

		toast.error('Gmail connection expired', {
			description: 'Please re-connect to keep your agents running.',
			duration: Number.POSITIVE_INFINITY,
			action: {
				label: 'Re-Connect',
				onClick: () => {
					toast.dismiss();
					goto('/dashboard/integrations');
				}
			}
		});
	}

	async function checkAndRecoverConnections() {
		try {
			const res = await api.get<ConnectionStatusResponse>('/api/connection/status');
			const google = res.integrations.find((i) => i.provider === 'google');

			if (google && google.is_connected) {
				if (google.needs_reconnect) {
					triggerReconnectAlert();
					return;
				}

				try {
					await api.get('/api/webhooks/listen-to-gmail');

					console.log('Gmail webhook silently verified/renewed.');
					gmailNeedsReconnect = false;
				} catch (err) {
					console.error('Silent webhook renewal failed', err);
					triggerReconnectAlert();
				}
			}
		} catch (err) {
			console.error('Failed to fetch connection status', err);
		}
	}

	onMount(() => {
		checkAndRecoverConnections();

		const interval = setInterval(checkAndRecoverConnections, 1000 * 60 * 45);
		return () => clearInterval(interval);
	});

</script>

<div class="flex min-h-screen flex-col">
	<header
		class="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
	>
		<nav class="flex h-14 items-center gap-6 px-6">
			<a
				href="/dashboard"
				class="flex items-center gap-2 text-sm font-medium transition-colors {$page.url.pathname ===
				'/dashboard'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<LayoutDashboard class="h-4 w-4" />
				Agents
			</a>

			<a
				href="/dashboard/new"
				class="flex items-center gap-2 text-sm font-medium transition-colors {$page.url.pathname ===
				'/dashboard/new'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<PlusCircle class="h-4 w-4" />
				New Agent
			</a>

			<a
				href="/dashboard/integrations"
				class="flex items-center gap-2 text-sm font-medium transition-colors {$page.url.pathname ===
				'/dashboard/integrations'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<Plug class="h-4 w-4" />
				Integrations
			</a>
		</nav>
	</header>

	{#if gmailNeedsReconnect}
		<div
			class="flex items-center justify-between bg-destructive/15 px-6 py-3 text-sm font-medium text-destructive"
		>
			<p>⚠️ Your Gmail connection requires authorization to continue processing automations.</p>
			<button
				class="text-destructive-foreground rounded-md bg-destructive px-3 py-1.5 transition-colors hover:bg-destructive/90"
				onclick={() => goto('/dashboard/integrations')}
			>
				Fix Connection
			</button>
		</div>
	{/if}

	<main class="flex-1 overflow-auto">
		{@render children()}
	</main>
</div>
