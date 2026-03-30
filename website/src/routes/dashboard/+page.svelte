<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Switch } from '$lib/components/ui/switch';
	import { Eye, Loader, Mail, Trash2, Play, Settings2, RefreshCw } from 'lucide-svelte';
	import { formatLabel } from '$lib/utils';
	import { toast, Toaster } from 'svelte-sonner';

	type WorkflowDef = components['schemas']['WorkflowDefinition-Output'];

	type Workflow = WorkflowDef & {
		id: string;
		is_active: boolean;
		config?: WorkflowDef;
	};

	let workflows = $state<Workflow[]>([]);
	let isLoading = $state(true);
	let runningIds = $state<Set<string>>(new Set());

	async function fetchWorkflows() {
		try {
			workflows = await api.get<Workflow[]>('/api/workflow/get_workflows');
		} catch (err: any) {
			toast.error('Failed to load workflows.');
			console.error('Failed to load workflows', err);
		} finally {
			isLoading = false;
		}
	}

	async function toggleWorkflow(id: string, currentStatus: boolean) {
		try {
			await api.patch('/api/workflow/toggle', {
				deployment_id: id,
				status: !currentStatus
			});
			await fetchWorkflows();
			toast.success('Workflow is now ', currentStatus);
		} catch (err) {
			toast.error('Failed to toggle workflow.');
			console.error('Toggle failed', err);
		}
	}

	async function runWorkflow(wf: Workflow) {
		const id = wf.id;

		if (!id) {
			console.error('No deployment ID found on this workflow object', wf);
			return;
		}

		if (runningIds.has(id)) return;

		runningIds.add(id);
		try {
			await api.post('/api/workflow/run', {
				deployment_id: id,
				config: {}
			});

			toast.success('Workflow triggered successfully.');
		} catch (err) {
			toast.error('Workflow run failed.');
			console.error('Manual run failed', err);
		} finally {
			setTimeout(() => {
				runningIds.delete(id);
			}, 1000);
		}
	}

	async function deleteWorkflow(id: string, name: string) {
		const confirmed = confirm(
			`Are you sure you want to delete "${name}"? This will stop all active runs and remove the agent permanently.`
		);
		if (!confirmed) return;

		try {
			await api.delete(`/api/workflow/delete?deployment_id=${id}`);
			await fetchWorkflows();
			toast.success(`Agent "${name}" deleted.`);
		} catch (err: any) {
			console.error('Delete failed', err);
			toast.error(err.detail || 'Failed to delete agent. Please try again.');
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
			<Loader class="h-8 w-8 animate-spin text-muted-foreground" />
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
						{@const triggerNodeId = wf.config?.start_node_ids?.[0]}
						{@const triggerNode = triggerNodeId ? wf.config?.nodes?.[triggerNodeId] : null}
						{@const triggerType = triggerNode?.config?.type}

						{#if triggerType === 'schedule' || triggerType === 'manual'}
							<button
								onclick={() => runWorkflow(wf)}
								disabled={runningIds.has(wf.id)}
								class="group flex w-full items-center justify-between rounded-md border bg-primary/5 p-2 text-xs font-semibold transition-colors hover:bg-primary/10"
							>
								<div class="flex items-center">
									{#if runningIds.has(wf.id)}
										<RefreshCw class="mr-2 h-3.5 w-3.5 animate-spin text-primary" />
									{:else}
										<Play
											class="mr-2 h-3.5 w-3.5 text-primary transition-transform group-hover:scale-110"
										/>
									{/if}
									TRIGGER: {formatLabel(triggerType)}
								</div>
								<span class="text-[10px] text-primary opacity-70">RUN NOW</span>
							</button>
						{:else}
							<div
								class="flex items-center rounded-md border bg-muted/50 p-2 text-xs font-semibold text-muted-foreground"
							>
								<Play class="mr-2 h-3.5 w-3.5 opacity-50" />
								TRIGGER: {formatLabel(triggerType || 'Unknown')}
							</div>
						{/if}

						<div class="space-y-2">
							<p class="text-[10px] font-bold text-muted-foreground uppercase">Automation Steps</p>
							<div class="flex flex-wrap gap-2">
								{#each Object.values(wf.config?.nodes || {}).filter((n) => n.type === 'action') as action}
									<Badge variant="outline" class="font-mono text-[10px] uppercase">
										{formatLabel(action.config.type)}
									</Badge>
								{/each}
							</div>
						</div>
					</Card.Content>

					<Card.Footer class="flex justify-between border-t bg-muted/20 pt-4">
						<div class="flex gap-2">
							<Button
								variant="ghost"
								size="sm"
								class="text-destructive hover:bg-destructive/10"
								onclick={() => deleteWorkflow(wf.id, wf.name)}
							>
								<Trash2 class="h-4 w-4" />
							</Button>
							<Button variant="ghost" size="sm" href="/dashboard/agent/{wf.id}/history">
								<Eye class="mr-1 h-4 w-4" /> History
							</Button>
						</div>
						<Button variant="secondary" size="sm" href="/dashboard/edit/{wf.id}">
							<Settings2 class="mr-1 h-4 w-4" /> Config
						</Button>
					</Card.Footer>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
