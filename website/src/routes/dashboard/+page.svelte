<script lang="ts">
	import { onMount } from 'svelte';
	import { authorizedFetch } from '$lib/api';
	import type { components } from '$lib/types/api';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Switch } from '$lib/components/ui/switch';
	import { Loader2, Mail, Slack, Trash2, Play, Settings2 } from 'lucide-svelte';
	import { goto } from '$app/navigation';

	type Workflow = components['schemas']['WorkflowDefinition'] & {
		deployment_id: string;
		active: boolean;
	};
	type ToggleRequest = components['schemas']['ToggleWorkflowRequest'];

	let workflows = $state<Workflow[]>([]);
	let isLoading = $state(true);

	const API_BASE_URL = 'http://backend:8000';

	async function fetchWorkflows() {
		const token = localStorage.getItem('access_token');
		if (!token) {
			goto('/login');
			return;
		}

		try {
			const res = await authorizedFetch(`${API_BASE_URL}/api/workflow/get_workflows`);
			if (res && res.ok) {
				// Backend returns an array of workflows matching our Workflow type
				workflows = await res.json();
			}
		} catch (err) {
			console.error('Failed to load workflows', err);
		} finally {
			isLoading = false;
		}
	}

	async function toggleWorkflow(id: string, currentStatus: boolean) {
		const payload: ToggleRequest = {
			deployment_id: id,
			status: !currentStatus
		};

		const res = await authorizedFetch(`${API_BASE_URL}/api/workflow/toggle`, {
			method: 'PATCH',
			body: JSON.stringify(payload)
		});

		if (res?.ok) {
			// Optimistic UI update or re-fetch
			fetchWorkflows();
		}
	}

	onMount(fetchWorkflows);
</script>

<div class="min-h-screen bg-background p-6 lg:p-10">
	<header class="mb-8 flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Agent Control Center</h1>
			<p class="text-muted-foreground">Monitoring {workflows.length} active automations.</p>
		</div>
		<Button href="/dashboard/new">Create New Agent</Button>
	</header>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center">
			<Loader2 class="h-8 w-8 animate-spin text-muted-foreground" />
		</div>
	{:else if workflows.length === 0}
		<Card.Root
			class="flex flex-col items-center justify-center border-dashed p-12 text-center shadow-none"
		>
			<div class="mb-4 rounded-full bg-muted p-4">
				<Mail class="h-8 w-8 text-muted-foreground" />
			</div>
			<Card.Title class="text-xl font-semibold">No Agents Deployed</Card.Title>
			<Card.Description>Your AI workforce is currently empty.</Card.Description>
		</Card.Root>
	{:else}
		<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
			{#each workflows as wf}
				<Card.Root>
					<Card.Header>
						<div class="flex items-center justify-between">
							<Badge variant={wf.is_active ? 'default' : 'secondary'}>
								{wf.is_active ? 'RUNNING' : 'PAUSED'}
							</Badge>
							<Switch
								checked={wf.is_active}
								onCheckedChange={() => toggleWorkflow(wf.id, wf.is_active)}
							/>
						</div>
						<Card.Title class="mt-4 text-xl font-bold">{wf.name}</Card.Title>
						<Card.Description class="line-clamp-2 italic">
							{wf.description}
						</Card.Description>
					</Card.Header>

					<Card.Content class="space-y-4">
						<div class="flex items-center rounded-md border bg-muted/50 p-2 text-xs font-semibold">
							<Play class="mr-2 h-3.5 w-3.5 text-primary" />
							TRIGGER: {wf.config?.trigger?.type?.replace('_', ' ') || 'Unknown'}
						</div>

						<div class="space-y-2">
							<p class="text-[10px] font-bold text-muted-foreground uppercase">Automation Steps</p>
							<div class="flex flex-wrap gap-2">
								{#each wf.config?.actions || [] as action}
									<Badge variant="outline" class="font-mono text-[10px] uppercase">
										{action.type.replace('_', ' ')}
									</Badge>
								{/each}
							</div>
						</div>
					</Card.Content>

					<Card.Footer class="flex justify-between border-t bg-muted/20 pt-4">
						<Button variant="ghost" size="sm" class="text-destructive hover:bg-destructive/10">
							<Trash2 class="h-4 w-4" />
						</Button>
						<Button variant="secondary" size="sm">
							<Settings2 class="mr-1 h-4 w-4" /> Config
						</Button>
					</Card.Footer>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
