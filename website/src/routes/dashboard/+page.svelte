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

	const API_BASE_URL = 'http://localhost:8000';

  async function fetchWorkflows() {
    const token = localStorage.getItem("access_token");
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

<div class="min-h-screen bg-slate-50 p-6 font-sans">
	<header class="mb-8 flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight text-slate-900">Agent Control Center</h1>
			<p class="font-medium text-slate-500">Monitoring {workflows.length} active automations.</p>
		</div>
		<a href="/dashboard/new">
			<Button
				class="rounded-none border-2 border-slate-900 bg-[#C7D2FE] text-slate-900 shadow-none hover:bg-[#A5B4FC]"
			>
				Create New Agent
			</Button>
		</a>
	</header>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center">
			<Loader2 class="h-8 w-8 animate-spin text-slate-400" />
		</div>
	{:else if workflows.length === 0}
		<Card.Root
			class="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 bg-transparent p-12 text-center shadow-none"
		>
			<div class="mb-4 rounded-full border-2 border-slate-900 bg-white p-4">
				<Mail class="h-8 w-8 text-slate-900" />
			</div>
			<Card.Title class="text-xl">No Agents Deployed</Card.Title>
			<Card.Description class="mt-2 font-medium"
				>Your AI workforce is currently empty.</Card.Description
			>
		</Card.Root>
	{:else}
		<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
			{#each workflows as wf}
				<Card.Root
					class="group relative rounded-none border-2 border-slate-900 bg-white shadow-none transition-all hover:-translate-y-1"
				>
					<Card.Header class="border-b-2 border-slate-900 bg-[#F8FAFC] pb-3">
						<div class="flex items-center justify-between">
							<Badge
								class="rounded-none border-2 border-slate-900 shadow-none {wf.active
									? 'bg-[#DCFCE7] text-slate-900'
									: 'bg-slate-200 text-slate-600'}"
							>
								{wf.active ? 'RUNNING' : 'PAUSED'}
							</Badge>
							<Switch
								checked={wf.active}
								onCheckedChange={() => toggleWorkflow(wf.deployment_id, wf.active)}
							/>
						</div>
						<Card.Title class="mt-4 text-xl font-bold tracking-tight uppercase"
							>{wf.name}</Card.Title
						>
						<Card.Description class="line-clamp-2 font-medium text-slate-600"
							>{wf.description}</Card.Description
						>
					</Card.Header>

					<Card.Content class="space-y-4 pt-6">
						<div
							class="flex items-center border-2 border-slate-900 bg-[#E0F2FE] p-2 text-xs font-bold uppercase"
						>
							<Play class="mr-2 h-4 w-4" />
							Trigger: {wf.trigger.type.replace('_', ' ')}
						</div>

						<div class="space-y-2">
							<p class="text-[10px] font-black text-slate-400 uppercase">Next Steps</p>
							<div class="flex flex-wrap gap-2">
								{#each wf.actions as action}
									<div class="border border-slate-900 bg-white px-2 py-1 text-[10px] font-bold">
										{action.type.toUpperCase()}
									</div>
								{/each}
							</div>
						</div>
					</Card.Content>

					<Card.Footer class="flex justify-between border-t-2 border-slate-900 bg-[#FFF7ED] p-3">
						<Button variant="ghost" size="sm" class="rounded-none text-destructive hover:bg-red-50">
							<Trash2 class="h-4 w-4" />
						</Button>
						<div class="flex gap-2">
							<Button
								variant="outline"
								size="sm"
								class="rounded-none border-2 border-slate-900 bg-white font-bold"
							>
								<Settings2 class="mr-1 h-4 w-4" /> Config
							</Button>
						</div>
					</Card.Footer>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
