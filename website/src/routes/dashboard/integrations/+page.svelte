<script lang="ts">
	import { onMount } from 'svelte';
	import { api, BASE_URL } from '$lib/api/client';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import {
		Loader2,
		Mail,
		MessageSquare,
		RefreshCw,
		AlertCircle,
		CheckCircle2,
		Settings2,
		Unplug,
		Info
	} from 'lucide-svelte';
	import { toast } from 'svelte-sonner';
	import { formatLabel } from '$lib/utils';

	type IntegrationStatus = {
		provider: string;
		is_connected: boolean;
		email: string | null;
		needs_reconnect: boolean;
	};

	type ConnectionStatusResponse = {
		integrations: IntegrationStatus[];
	};

	let integrations = $state<IntegrationStatus[]>([]);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let syncingProviders = $state<Set<string>>(new Set());

	async function fetchIntegrations() {
		isLoading = true;
		error = null;
		try {
			const res = await api.get<ConnectionStatusResponse>('/api/connection/status');
			integrations = res.integrations;
		} catch (err: any) {
			console.error('Failed to load integrations', err);
			error = err.detail || 'Failed to load connection statuses.';
			toast.error(error);
		} finally {
			isLoading = false;
		}
	}

	async function syncWebhook(provider: string) {
		if (syncingProviders.has(provider)) return;

		if (provider !== 'google') {
			toast.info(`Sync is not yet supported for ${formatLabel(provider)}.`, {
				icon: Info
			});
			return;
		}

		syncingProviders.add(provider);

		try {
			await api.get('/api/webhooks/listen-to-gmail');
			toast.success('Gmail webhook synced successfully!');
		} catch (err: any) {
			console.error(`Failed to sync ${provider}`, err);
			const message =
				err.detail || `Failed to sync ${formatLabel(provider)}. You may need to reconnect.`;
			toast.error(message);
			await fetchIntegrations();
		} finally {
			syncingProviders.delete(provider);
		}
	}

	function handleConnect(provider: string) {
		window.location.href = `${BASE_URL}/api/auth/connect/${provider}`;
	}

	function getProviderIcon(provider: string) {
		switch (provider.toLowerCase()) {
			case 'google':
				return Mail;
			case 'discord':
				return MessageSquare;
			default:
				return Settings2;
		}
	}

	onMount(fetchIntegrations);
</script>

<div class="min-h-screen bg-background p-6 lg:p-10">
	<header class="mb-8">
		<h1 class="text-3xl font-bold tracking-tight">Integrations</h1>
		<p class="text-muted-foreground">
			Connect your tools to allow your AI agents to interact with them.
		</p>
	</header>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center">
			<Loader2 class="h-8 w-8 animate-spin text-muted-foreground" />
		</div>
	{:else if error}
		<div class="flex h-64 flex-col items-center justify-center gap-4 text-center">
			<div class="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
				<AlertCircle class="h-6 w-6 text-destructive" />
			</div>
			<div>
				<h3 class="text-lg font-semibold">Unable to load integrations</h3>
				<p class="text-sm text-muted-foreground">{error}</p>
			</div>
			<Button variant="outline" onclick={fetchIntegrations}>
				<RefreshCw class="mr-2 h-4 w-4" /> Try Again
			</Button>
		</div>
	{:else}
		<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
			{#each integrations as integration}
				{@const Icon = getProviderIcon(integration.provider)}

				<Card.Root
					class="relative flex flex-col justify-between overflow-hidden transition-all hover:border-primary/50"
				>
					<Card.Header>
						<div class="flex items-start justify-between">
							<div class="flex h-12 w-12 items-center justify-center rounded-lg bg-muted">
								<div class="relative">
									<Icon
										class="h-6 w-6 {integration.is_connected && !integration.needs_reconnect
											? 'text-foreground'
											: 'text-muted-foreground'}"
									/>
									{#if integration.is_connected && !integration.needs_reconnect}
										<div class="absolute -right-1 -bottom-1 rounded-full bg-background p-0.5">
											<CheckCircle2 class="h-3 w-3 text-green-500" />
										</div>
									{:else if integration.is_connected && integration.needs_reconnect}
										<div class="absolute -right-1 -bottom-1 rounded-full bg-background p-0.5">
											<AlertCircle class="h-3 w-3 text-destructive" />
										</div>
									{/if}
								</div>
							</div>

							{#if integration.is_connected}
								{#if integration.needs_reconnect}
									<Badge variant="destructive" class="uppercase">Action Required</Badge>
								{:else}
									<Badge
										variant="default"
										class="bg-green-500/15 text-green-700 uppercase hover:bg-green-500/25 dark:bg-green-500/20 dark:text-green-400"
									>
										Active
									</Badge>
								{/if}
							{/if}
						</div>

						<Card.Title class="mt-4 text-xl capitalize">{integration.provider}</Card.Title>
						<Card.Description>
							{#if integration.is_connected && integration.email}
								Connected as <span class="font-medium text-foreground">{integration.email}</span>
							{:else if integration.provider === 'google'}
								Grant access to read and send emails on your behalf.
							{:else}
								Connect to interact with {formatLabel(integration.provider)}.
							{/if}
						</Card.Description>
					</Card.Header>

					<Card.Footer
						class="flex flex-col gap-3 border-t bg-muted/20 pt-4 sm:flex-row sm:items-center sm:justify-between"
					>
						{#if !integration.is_connected}
							<Button class="w-full" onclick={() => handleConnect(integration.provider)}>
								Connect {formatLabel(integration.provider)}
							</Button>
						{/if}

						{#if integration.is_connected}
							{#if integration.needs_reconnect}
								<Button
									variant="destructive"
									class="w-full"
									onclick={() => handleConnect(integration.provider)}
								>
									<Unplug class="mr-2 h-4 w-4" /> Re-Connect
								</Button>
							{:else}
								<div class="flex w-full items-center gap-2">
									<Button
										variant="outline"
										class="flex-1"
										disabled={syncingProviders.has(integration.provider)}
										onclick={() => syncWebhook(integration.provider)}
									>
										{#if syncingProviders.has(integration.provider)}
											<RefreshCw class="mr-2 h-4 w-4 animate-spin" /> Syncing...
										{:else}
											<RefreshCw class="mr-2 h-4 w-4" /> Sync Webhook
										{/if}
									</Button>
									<Button variant="ghost" size="icon" title="Settings">
										<Settings2 class="h-4 w-4" />
									</Button>
								</div>
							{/if}
						{/if}
					</Card.Footer>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
