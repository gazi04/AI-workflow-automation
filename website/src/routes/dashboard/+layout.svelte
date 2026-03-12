<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { toast, Toaster } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { LayoutDashboard, CirclePlus, Plug, LogOut, User, History } from 'lucide-svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { workflowStore } from '$lib/workflowStore.svelte';
  import { decodeJwtPayload, logout } from '$lib/utils';

	let { children } = $props();

	let gmailNeedsReconnect = $state(false);
	let userEmail = $state<string | null>(null);
	let userId = $state<string | null>(null);
	let userInitials = $state('?');
	let socket: WebSocket | null = null;

	type IntegrationStatus = {
		provider: string;
		is_connected: boolean;
		email: string | null;
		needs_reconnect: boolean;
	};

	type ConnectionStatusResponse = {
		integrations: IntegrationStatus[];
	};

	function loadUserFromToken() {
		if (typeof window === 'undefined') return;
		const token = localStorage.getItem('access_token');
		if (!token) return;

		const payload = decodeJwtPayload(token);
		if (payload) {
			if (typeof payload.email === 'string') {
				userEmail = payload.email;
				userInitials = userEmail.slice(0, 2).toUpperCase();
			}
			if (typeof payload.sub === 'string') {
				userId = payload.sub;
			}
		}
	}

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

	type WorkflowRun = {
		id: string;
		name: string;
		state_name: string;
		deployment_name?: string;
		deployment_id?: string;
	};

	let knownRunStates = new Map<string, string>();

	async function initWorkflowWebSocket() {
		if (!userId) return;

		const wsUrl = `ws://localhost:8000/api/workflow/ws/workflows/${userId}`;
		socket = new WebSocket(wsUrl);

		socket.onmessage = (event) => {
			const message = JSON.parse(event.data);
			if (message.type === 'workflow_update') {
				const latestRuns: WorkflowRun[] = message.data;
				
				workflowStore.setLatestRuns(latestRuns);

				for (const run of latestRuns) {
					const lastState = knownRunStates.get(run.id);

					if (lastState && lastState !== 'Failed' && run.state_name === 'Failed') {
						toast.error(`Agent Run Failed: ${run.name}`, {
							description: 'The execution encountered an error.',
							action: {
								label: 'View Logs',
								onClick: () => {
									const targetId = run.deployment_id || '';
									goto(`/dashboard/agent/${targetId}/history?runId=${run.id}`);
								}
							}
						});
					}

					knownRunStates.set(run.id, run.state_name);
				}
			} else if (message.type === 'notification') {
        console.log('Message  was sent from back to front.');
				toast.success(message.message);
			}
		};

		socket.onclose = () => {
			console.log('Workflow WebSocket closed. Retrying in 5s...');
			setTimeout(initWorkflowWebSocket, 5000);
		};

		socket.onerror = (err) => {
			console.error('Workflow WebSocket error:', err);
		};
	}

	onMount(() => {
		loadUserFromToken();
		checkAndRecoverConnections();
		initWorkflowWebSocket();

		const connInterval = setInterval(checkAndRecoverConnections, 1000 * 60 * 45);

		return () => {
			clearInterval(connInterval);
			if (socket) socket.close();
		};
	});
</script>

<div class="flex min-h-screen flex-col">
	<header
		class="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60"
	>
		<nav class="flex h-14 items-center gap-6 px-6">
			<a
				href="/dashboard"
				class="flex items-center gap-2 text-sm font-medium transition-colors {page.url.pathname ===
				'/dashboard'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<LayoutDashboard class="h-4 w-4" />
				Agents
			</a>

			<a
				href="/dashboard/new"
				class="flex items-center gap-2 text-sm font-medium transition-colors {page.url.pathname ===
				'/dashboard/new'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<CirclePlus class="h-4 w-4" />
				New Agent
			</a>

			<a
				href="/dashboard/integrations"
				class="flex items-center gap-2 text-sm font-medium transition-colors {page.url.pathname ===
				'/dashboard/integrations'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<Plug class="h-4 w-4" />
				Integrations
			</a>

			<a
				href="/dashboard/history"
				class="flex items-center gap-2 text-sm font-medium transition-colors {page.url.pathname ===
				'/dashboard/history'
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<History class="h-4 w-4" />
				History
			</a>

			<div class="ml-auto">
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						<button
							class="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground transition-opacity hover:opacity-80"
							title={userEmail ?? 'Profile'}
						>
							{#if userEmail}
								{userInitials}
							{:else}
								<User class="h-4 w-4" />
							{/if}
						</button>
					</DropdownMenu.Trigger>

					<DropdownMenu.Content align="end" class="w-56">
						<DropdownMenu.Label>
							<p class="text-xs text-muted-foreground">Signed in as</p>
							<p class="truncate text-sm font-medium">{userEmail ?? '...'}</p>
						</DropdownMenu.Label>
						<DropdownMenu.Separator />
						<DropdownMenu.Item
							class="cursor-pointer text-destructive focus:text-destructive"
							onclick={logout}
						>
							<LogOut class="mr-2 h-4 w-4" />
							Log out
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
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

<Toaster richColors position="bottom-right" />
