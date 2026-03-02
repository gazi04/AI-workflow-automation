<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import * as Card from '$lib/components/ui/card';
	import { Loader2, ArrowLeft, Calendar, Clock, Activity, History } from 'lucide-svelte';
	import { formatLabel } from '$lib/utils';
	import { toast } from 'svelte-sonner';

	type WorkflowRun = {
		id: string;
		name: string;
		state_name: string;
		start_time: string;
		total_run_time: number;
	};

	const id = page.params.id;
	let runs = $state<WorkflowRun[]>([]);
	let workflowName = $state('');
	let isLoading = $state(true);

	async function fetchHistory() {
		try {
			// Fetch workflow details to get the name
			const wf = await api.get<any>(`/api/workflow/get_workflow/${id}`);
			workflowName = wf.name;

			// Fetch history
			runs = await api.get<WorkflowRun[]>(`/api/workflow/${id}/history`);
		} catch (err: any) {
			toast.error('Failed to load history.');
			console.error('Failed to load history', err);
		} finally {
			isLoading = false;
		}
	}

	function formatDate(dateStr: string | null) {
		if (!dateStr) return 'N/A';
		const date = new Date(dateStr);
		return date.toLocaleString();
	}

	function formatDuration(seconds: number) {
		if (seconds < 60) return `${seconds.toFixed(1)}s`;
		const mins = Math.floor(seconds / 60);
		const secs = (seconds % 60).toFixed(0);
		return `${mins}m ${secs}s`;
	}

	function getStatusVariant(status: string) {
		switch (status?.toUpperCase()) {
			case 'COMPLETED':
				return 'default';
			case 'FAILED':
				return 'destructive';
			case 'RUNNING':
				return 'secondary';
			default:
				return 'outline';
		}
	}

	onMount(fetchHistory);
</script>

<div class="min-h-screen bg-background p-6 lg:p-10">
	<header class="mb-8 items-center justify-between">
		<div class="mb-4">
			<Button variant="ghost" size="sm" href="/dashboard" class="mb-2">
				<ArrowLeft class="mr-2 h-4 w-4" /> Back to Dashboard
			</Button>
			<div class="flex items-center gap-3">
				<div class="rounded-full bg-primary/10 p-3">
					<History class="h-6 w-6 text-primary" />
				</div>
				<div>
					<h1 class="text-3xl font-bold tracking-tight">Execution History</h1>
					<p class="text-muted-foreground">
						Agent: <span class="font-semibold text-foreground">{workflowName || 'Loading...'}</span>
					</p>
				</div>
			</div>
		</div>
	</header>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center">
			<Loader2 class="h-8 w-8 animate-spin text-muted-foreground" />
		</div>
	{:else if runs.length === 0}
		<Card.Root
			class="flex flex-col items-center justify-center border-dashed p-12 text-center shadow-none"
		>
			<div class="mb-4 rounded-full bg-muted p-4">
				<Activity class="h-8 w-8 text-muted-foreground" />
			</div>
			<Card.Title class="text-xl font-semibold">No History Found</Card.Title>
			<Card.Description>This agent hasn't been triggered yet.</Card.Description>
		</Card.Root>
	{:else}
		<div class="overflow-hidden rounded-xl border bg-card shadow-sm">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead class="bg-muted/50 text-xs font-medium text-muted-foreground uppercase">
						<tr>
							<th class="px-6 py-4">Status</th>
							<th class="px-6 py-4">Run Name</th>
							<th class="px-6 py-4">Started At</th>
							<th class="px-6 py-4">Duration</th>
							<th class="px-6 py-4 text-right">Actions</th>
						</tr>
					</thead>
					<tbody class="divide-y">
						{#each runs as run}
							<tr class="transition-colors hover:bg-muted/30">
								<td class="px-6 py-4 whitespace-nowrap">
									<Badge variant={getStatusVariant(run.state_name)}>
										{run.state_name || 'UNKNOWN'}
									</Badge>
								</td>
								<td class="px-6 py-4 font-mono font-medium">{run.name}</td>
								<td class="px-6 py-4 whitespace-nowrap text-muted-foreground">
									<div class="flex items-center">
										<Calendar class="mr-2 h-3.5 w-3.5 opacity-70" />
										{formatDate(run.start_time)}
									</div>
								</td>
								<td class="px-6 py-4 whitespace-nowrap text-muted-foreground">
									<div class="flex items-center">
										<Clock class="mr-2 h-3.5 w-3.5 opacity-70" />
										{formatDuration(run.total_run_time)}
									</div>
								</td>
								<td class="px-6 py-4 text-right">
									<Button variant="outline" size="sm" disabled>View Logs</Button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
