<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';

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

<main class="flex-1">
	{@render children()}
</main>
