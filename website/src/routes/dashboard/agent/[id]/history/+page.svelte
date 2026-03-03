<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import * as Card from '$lib/components/ui/card';
	import {
		Loader2,
		ArrowLeft,
		Calendar,
		Clock,
		Activity,
		History,
		X,
		Terminal,
		ExternalLink
	} from 'lucide-svelte';
	import { formatLabel } from '$lib/utils';
	import { toast } from 'svelte-sonner';
	import { fly, fade } from 'svelte/transition';

	type WorkflowRun = {
		id: string;
		name: string;
		state_name: string;
		start_time: string;
		total_run_time: number;
	};

	const id = page.params.id;
	const urlRunId = page.url.searchParams.get('runId');

	let runs = $state<WorkflowRun[]>([]);
	let workflowName = $state('');
	let isLoading = $state(true);

	// Drawer state
	let selectedRun = $state<WorkflowRun | null>(null);
	let logs = $state<string>('');
	let isLoadingLogs = $state(false);

	async function fetchHistory() {
		try {
			// Fetch workflow details to get the name
			const wf = await api.get<any>(`/api/workflow/get_workflow/${id}`);
			workflowName = wf.name;

			// Fetch history
			runs = await api.get<WorkflowRun[]>(`/api/workflow/${id}/history`);

			// Deep-link check: Auto-open run if runId is in URL
			if (urlRunId) {
				const runToOpen = runs.find((r) => r.id === urlRunId);
				if (runToOpen) {
					openRunDetails(runToOpen);
				}
			}
		} catch (err: any) {
			toast.error('Failed to load history.');
			console.error('Failed to load history', err);
		} finally {
			isLoading = false;
		}
	}

	async function openRunDetails(run: WorkflowRun) {
		selectedRun = run;
		logs = '';
		isLoadingLogs = true;

		try {
			const logEntries = await api.get<any[]>(`/api/workflow/runs/${run.id}/logs`);
			logs = logEntries.map((l) => `[${l.level}] ${l.message}`).join('\n');
		} catch (err) {
			toast.error('Failed to load logs.');
			logs = 'Error: Could not retrieve logs for this run.';
		} finally {
			isLoadingLogs = false;
		}
	}

	function closeDrawer() {
		selectedRun = null;
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
							<tr
								class="group cursor-pointer transition-colors hover:bg-muted/30"
								onclick={() => openRunDetails(run)}
							>
								<td class="whitespace-nowrap px-6 py-4">
									<Badge variant={getStatusVariant(run.state_name)}>
										{run.state_name || 'UNKNOWN'}
									</Badge>
								</td>
								<td class="px-6 py-4 font-mono font-medium">{run.name}</td>
								<td class="whitespace-nowrap px-6 py-4 text-muted-foreground">
									<div class="flex items-center">
										<Calendar class="mr-2 h-3.5 w-3.5 opacity-70" />
										{formatDate(run.start_time)}
									</div>
								</td>
								<td class="whitespace-nowrap px-6 py-4 text-muted-foreground">
									<div class="flex items-center">
										<Clock class="mr-2 h-3.5 w-3.5 opacity-70" />
										{formatDuration(run.total_run_time)}
									</div>
								</td>
								<td class="px-6 py-4 text-right text-primary opacity-0 group-hover:opacity-100">
									<div class="flex items-center justify-end font-semibold">
										VIEW LOGS <ExternalLink class="ml-1.5 h-3.5 w-3.5" />
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- Run Detail Drawer -->
	{#if selectedRun}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="fixed inset-0 z-50 flex justify-end bg-background/80 backdrop-blur-sm"
			transition:fade={{ duration: 200 }}
			onclick={closeDrawer}
		>
			<div
				class="flex h-full w-full flex-col border-l bg-card shadow-2xl md:w-[600px] lg:w-[800px]"
				transition:fly={{ x: 200, duration: 300 }}
				onclick={(e) => e.stopPropagation()}
			>
				<div class="flex items-center justify-between border-b p-6">
					<div class="flex items-center gap-3">
						<div class="rounded-full bg-primary/10 p-2">
							<Terminal class="h-5 w-5 text-primary" />
						</div>
						<div>
							<h3 class="font-bold tracking-tight">Execution Logs</h3>
							<p class="text-xs text-muted-foreground uppercase">{selectedRun.name}</p>
						</div>
					</div>
					<Button variant="ghost" size="icon" onclick={closeDrawer}>
						<X class="h-4 w-4" />
					</Button>
				</div>

				<div class="flex-1 overflow-auto p-6">
					<div class="mb-6 grid grid-cols-2 gap-4 rounded-lg bg-muted/40 p-4 text-sm">
						<div>
							<span class="text-xs font-semibold uppercase text-muted-foreground">Status</span>
							<div class="mt-1">
								<Badge variant={getStatusVariant(selectedRun.state_name)}>
									{selectedRun.state_name}
								</Badge>
							</div>
						</div>
						<div>
							<span class="text-xs font-semibold uppercase text-muted-foreground">Time Started</span
							>
							<p class="mt-1 font-medium">{formatDate(selectedRun.start_time)}</p>
						</div>
						<div>
							<span class="text-xs font-semibold uppercase text-muted-foreground">Duration</span>
							<p class="mt-1 font-medium">{formatDuration(selectedRun.total_run_time)}</p>
						</div>
						<div>
							<span class="text-xs font-semibold uppercase text-muted-foreground">Run ID</span>
							<p class="mt-1 font-mono text-[10px] break-all">{selectedRun.id}</p>
						</div>
					</div>

					<div class="relative rounded-lg bg-slate-950 p-4 font-mono text-[13px] text-slate-300">
						<div class="mb-2 flex items-center gap-2 border-b border-slate-800 pb-2">
							<div class="flex gap-1.5">
								<div class="h-2.5 w-2.5 rounded-full bg-red-500/50"></div>
								<div class="h-2.5 w-2.5 rounded-full bg-yellow-500/50"></div>
								<div class="h-2.5 w-2.5 rounded-full bg-green-500/50"></div>
							</div>
							<span class="text-[10px] font-bold uppercase tracking-wider text-slate-500"
								>Terminal Logs</span
							>
						</div>

						{#if isLoadingLogs}
							<div class="flex items-center justify-center py-12">
								<Loader2 class="h-6 w-6 animate-spin text-slate-600" />
							</div>
						{:else if logs}
							<pre class="whitespace-pre-wrap leading-relaxed">{logs}</pre>
						{:else}
							<p class="italic text-slate-600">No logs available for this run.</p>
						{/if}
					</div>
				</div>

				<div class="border-t bg-muted/20 p-6">
					<Button class="w-full" variant="outline" onclick={closeDrawer}>Close Details</Button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	/* Subtle custom scrollbar for terminal */
	pre::-webkit-scrollbar {
		width: 6px;
	}
	pre::-webkit-scrollbar-track {
		background: transparent;
	}
	pre::-webkit-scrollbar-thumb {
		background: rgba(255, 255, 255, 0.1);
		border-radius: 10px;
	}
</style>
