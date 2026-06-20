<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import * as Card from '$lib/components/ui/card';
	import { formatDate, formatDuration } from '$lib/utils';
	import {
		Loader,
		ArrowLeft,
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

	type WorkflowRun = components['schemas']['WorkflowRun'];
	type WorkflowRunDetail = components['schemas']['WorkflowRunDetail'];

	const id = $derived(page.params.id);
	const urlRunId = $derived(page.url.searchParams.get('runId'));

	let runs = $state<WorkflowRun[]>([]);
	let workflowName = $state('');
	let isLoading = $state(true);
	// node id -> friendly label (e.g. "send_email") from the workflow config
	let nodeLabels = $state<Record<string, string>>({});

	let selectedRun = $state<WorkflowRun | null>(null);
	let logs = $state<string>('');
	let isLoadingLogs = $state(false);
	let audit = $state<WorkflowRunDetail | null>(null);
	let isLoadingAudit = $state(false);

	async function fetchHistory() {
		try {
			const wf = await api.get<any>(`/api/workflow/get_workflow/${id}`);
			workflowName = wf.name;

			const nodes = wf?.execution_config?.nodes ?? {};
			nodeLabels = Object.fromEntries(
				Object.entries(nodes).map(([nodeId, n]: [string, any]) => [
					nodeId,
					n?.config?.type ?? n?.type ?? nodeId
				])
			);

			runs = await api.get<WorkflowRun[]>(`/api/workflow/${id}/history`);

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
		audit = null;
		isLoadingAudit = true;

		// Per-node audit (workflow_runs table). 404 = run predates the audit log → no data.
		api
			.get<WorkflowRunDetail>(`/api/workflow/runs/${run.id}/audit`)
			.then((data) => (audit = data))
			.catch(() => (audit = null))
			.finally(() => (isLoadingAudit = false));

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

	function nodeStatusVariant(status: string) {
		return status === 'success' ? 'default' : status === 'failed' ? 'destructive' : 'secondary';
	}

	function pretty(value: unknown) {
		if (value === null || value === undefined) return '';
		if (typeof value === 'string') return value;
		return JSON.stringify(value, null, 2);
	}

	function closeDrawer() {
		selectedRun = null;
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
			<Loader class="h-8 w-8 animate-spin text-muted-foreground" />
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

					<!-- Per-node execution audit (workflow_runs) -->
					<div class="mb-6">
						<h4 class="mb-3 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
							Node Results
						</h4>

						{#if isLoadingAudit}
							<div class="flex items-center justify-center py-8">
								<Loader class="h-5 w-5 animate-spin text-muted-foreground" />
							</div>
						{:else if audit}
							<div
								class="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg bg-muted/40 p-3 text-sm"
							>
								<div class="flex items-center gap-2">
									<span class="text-xs text-muted-foreground uppercase">Outcome</span>
									<Badge variant={nodeStatusVariant(audit.status)}>{audit.status}</Badge>
								</div>
								{#if audit.duration_ms != null}
									<div class="flex items-center gap-2">
										<span class="text-xs text-muted-foreground uppercase">Duration</span>
										<span class="font-medium">{formatDuration(audit.duration_ms / 1000)}</span>
									</div>
								{/if}
							</div>

							<div class="space-y-3">
								{#each Object.entries(audit.node_results ?? {}) as [nodeId, result] (nodeId)}
									<div class="rounded-lg border bg-card p-3">
										<div class="flex items-center justify-between gap-2">
											<span class="font-mono text-sm font-medium">
												{nodeLabels[nodeId] ?? nodeId}
											</span>
											<Badge variant={nodeStatusVariant(result.status)}>{result.status}</Badge>
										</div>
										<p class="mt-0.5 font-mono text-[10px] text-muted-foreground">{nodeId}</p>

										{#if result.error}
											<div class="mt-2 rounded bg-destructive/10 p-2 text-xs text-destructive">
												<pre class="whitespace-pre-wrap">{result.error}</pre>
											</div>
										{/if}

										{#if result.output !== null && result.output !== undefined}
											<div class="mt-2">
												<span class="text-[10px] font-semibold text-muted-foreground uppercase"
													>Output</span
												>
												<pre
													class="mt-1 max-h-48 overflow-auto rounded bg-muted/50 p-2 text-xs whitespace-pre-wrap">{pretty(
														result.output
													)}</pre>
											</div>
										{/if}
									</div>
								{/each}
							</div>

							{#if audit.trigger_data}
								<div class="mt-4">
									<h5
										class="mb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase"
									>
										Trigger Data
									</h5>
									<pre
										class="max-h-48 overflow-auto rounded-lg bg-muted/50 p-3 text-xs whitespace-pre-wrap">{pretty(
											audit.trigger_data
										)}</pre>
								</div>
							{/if}
						{:else}
							<p class="rounded-lg bg-muted/30 p-3 text-sm text-muted-foreground italic">
								No node-level data for this run.
							</p>
						{/if}
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
