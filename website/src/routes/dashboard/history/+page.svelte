<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Input } from '$lib/components/ui/input';
	import * as Card from '$lib/components/ui/card';
	import {
		Loader,
		Search,
		Calendar,
		Clock,
		Activity,
		History,
		X,
		Terminal,
		ExternalLink
	} from 'lucide-svelte';
	import { toast, Toaster } from 'svelte-sonner';
	import { fly, fade } from 'svelte/transition';
	import { workflowStore } from '$lib/store/workflowStore.svelte';
	import type { components } from '$lib/types/schema';

	type WorkflowRun = components['schemas']['WorkflowRun'];

	let allRuns = $state<WorkflowRun[]>([]);
	let filteredRuns = $state<WorkflowRun[]>([]);
	let isLoading = $state(true);
	let searchQuery = $state('');
	let statusFilter = $state('ALL');

	let selectedRun = $state<WorkflowRun | null>(null);
	let logs = $state<string>('');
	let isLoadingLogs = $state(false);

	async function fetchAllHistory() {
		try {
			allRuns = await api.get<WorkflowRun[]>('/api/workflow/histories');
			applyFilters();
		} catch (err: any) {
			toast.error('Failed to load global history.');
			console.error('Failed to load history', err);
		} finally {
			isLoading = false;
		}
	}

	function applyFilters() {
		// Merge allRuns with latest updates from the global store
		const runMap = new Map(allRuns.map((r) => [r.id, r]));

		// Update or add runs from the global store
		for (const run of workflowStore.latestRuns) {
			runMap.set(run.id, run);
		}

		// Convert back to array and sort by start_time DESC
		const mergedRuns = Array.from(runMap.values()).sort((a, b) => {
			const dateA = new Date(a.start_time || 0).getTime();
			const dateB = new Date(b.start_time || 0).getTime();
			return dateB - dateA;
		});

		filteredRuns = mergedRuns.filter((run) => {
			const matchesSearch =
				run.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				(run.state_name || '').toLowerCase().includes(searchQuery.toLowerCase());
			const matchesStatus = statusFilter === 'ALL' || run.state_name === statusFilter;
			return matchesSearch && matchesStatus;
		});
	}

	async function openRunDetails(run: WorkflowRun) {
		selectedRun = run;
		logs = '';
		isLoadingLogs = true;

		try {
			const logEntries = await api.get<any[]>(`/api/workflow/runs/${run.id}/logs`);
			// Format logs: Prefect logs are usually a list of objects with a 'message' field
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

	function formatDate(dateStr: string | null | undefined) {
		if (!dateStr) return 'N/A';
		return new Date(dateStr).toLocaleString();
	}

	function formatDuration(seconds: number) {
		if (seconds < 60) return `${seconds.toFixed(1)}s`;
		return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
	}

	function getStatusVariant(status: string | null | undefined) {
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

	$effect(() => {
		// This will re-run applyFilters whenever allRuns, workflowStore.latestRuns,
		// searchQuery, or statusFilter changes.
		// Note: accessing workflowStore.latestRuns makes this effect reactive to it.
		const _trigger = workflowStore.latestRuns;
		applyFilters();
	});

	onMount(fetchAllHistory);
</script>

<div class="relative min-h-screen bg-background p-6 lg:p-10">
	<header class="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
		<div class="flex items-center gap-3">
			<div class="rounded-full bg-primary/10 p-3">
				<History class="h-6 w-6 text-primary" />
			</div>
			<div>
				<h1 class="text-3xl font-bold tracking-tight">Global History</h1>
				<p class="text-muted-foreground">Monitoring all agent activity across your workspace.</p>
			</div>
		</div>

		<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
			<div class="relative w-full sm:w-64">
				<Search class="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
				<Input placeholder="Search agents or status..." class="pl-9" bind:value={searchQuery} />
			</div>
			<select
				class="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
				bind:value={statusFilter}
			>
				<option value="ALL">All Statuses</option>
				<option value="COMPLETED">Completed</option>
				<option value="FAILED">Failed</option>
				<option value="RUNNING">Running</option>
			</select>
		</div>
	</header>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center">
			<Loader class="h-8 w-8 animate-spin text-muted-foreground" />
		</div>
	{:else if filteredRuns.length === 0}
		<Card.Root
			class="flex flex-col items-center justify-center border-dashed p-12 text-center shadow-none"
		>
			<div class="mb-4 rounded-full bg-muted p-4">
				<Activity class="h-8 w-8 text-muted-foreground" />
			</div>
			<Card.Title class="text-xl font-semibold">No History Found</Card.Title>
			<Card.Description>
				{searchQuery || statusFilter !== 'ALL'
					? "Try adjusting your filters to find what you're looking for."
					: "Your agents haven't performed any tasks yet."}
			</Card.Description>
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
							<th class="px-6 py-4 text-right">Details</th>
						</tr>
					</thead>
					<tbody class="divide-y">
						{#each filteredRuns as run}
							<tr
								class="group cursor-pointer transition-colors hover:bg-muted/30"
								onclick={() => openRunDetails(run)}
							>
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
				class="flex h-full w-full flex-col border-l bg-card shadow-2xl md:w-150 lg:w-200"
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
							<span class="text-xs font-semibold text-muted-foreground uppercase">Status</span>
							<div class="mt-1">
								<Badge variant={getStatusVariant(selectedRun.state_name)}>
									{selectedRun.state_name}
								</Badge>
							</div>
						</div>
						<div>
							<span class="text-xs font-semibold text-muted-foreground uppercase">Time Started</span
							>
							<p class="mt-1 font-medium">{formatDate(selectedRun.start_time)}</p>
						</div>
						<div>
							<span class="text-xs font-semibold text-muted-foreground uppercase">Duration</span>
							<p class="mt-1 font-medium">{formatDuration(selectedRun.total_run_time)}</p>
						</div>
						<div>
							<span class="text-xs font-semibold text-muted-foreground uppercase">Run ID</span>
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
							<span class="text-[10px] font-bold tracking-wider text-slate-500 uppercase"
								>Terminal Logs</span
							>
						</div>

						{#if isLoadingLogs}
							<div class="flex items-center justify-center py-12">
								<Loader class="h-6 w-6 animate-spin text-slate-600" />
							</div>
						{:else if logs}
							<pre class="leading-relaxed whitespace-pre-wrap">{logs}</pre>
						{:else}
							<p class="text-slate-600 italic">No logs available for this run.</p>
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
