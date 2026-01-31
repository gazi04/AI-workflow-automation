<script lang="ts">
	import { onMount } from "svelte";
	import { authorizedFetch } from "$lib/api";
	import * as Card from "$lib/components/ui/card";
	import { Button } from "$lib/components/ui/button";
	import { Badge } from "$lib/components/ui/badge";
	import { Switch } from "$lib/components/ui/switch";
	import { Loader2, Mail, Slack, Trash2, Play } from "lucide-svelte";

	let workflows = $state([]);
	let isLoading = $state(true);

	const API_BASE_URL = "http://localhost:8000";

	async function fetchWorkflows() {
		try {
			const res = await authorizedFetch(`${API_BASE_URL}/api/workflow/get_workflows`);
			if (res && res.ok) {
				workflows = await res.json();
			}
		} catch (err) {
			console.error("Failed to load workflows", err);
		} finally {
			isLoading = false;
		}
	}

	async function toggleWorkflow(id: string, currentStatus: boolean) {
		const res = await authorizedFetch(`${API_BASE_URL}/api/workflow/toggle`, {
			method: "PATCH",
			body: JSON.stringify({ deployment_id: id, status: !currentStatus })
		});
		if (res?.ok) fetchWorkflows(); // Refresh list
	}

	onMount(fetchWorkflows);
</script>

<div class="min-h-screen bg-slate-50 p-6">
	<header class="mb-8 flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Your Workflows</h1>
			<p class="text-muted-foreground">Manage your AI email automation agents.</p>
		</div>
		<Button class="bg-primary hover:bg-primary/90">
			+ New Workflow
		</Button>
	</header>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center">
			<Loader2 class="h-8 w-8 animate-spin text-primary" />
		</div>
	{:else if workflows.length === 0}
		<Card.Root class="border-dashed border-2 flex flex-col items-center justify-center p-12 text-center">
			<Mail class="h-12 w-12 text-muted-foreground mb-4" />
			<Card.Title>No workflows found</Card.Title>
			<Card.Description>Create your first AI agent to start automating.</Card.Description>
		</Card.Root>
	{:else}
		<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
			{#each workflows as wf}
				<Card.Root class="overflow-hidden shadow-none border-2 hover:border-primary/50 transition-colors">
					<Card.Header class="pb-3 border-b bg-white">
						<div class="flex justify-between items-start">
							<Badge variant={wf.active ? "default" : "secondary"}>
								{wf.active ? "Active" : "Paused"}
							</Badge>
							<Switch 
								checked={wf.active} 
								onCheckedChange={() => toggleWorkflow(wf.deployment_id, wf.active)} 
							/>
						</div>
						<Card.Title class="mt-4 text-xl">{wf.name}</Card.Title>
						<Card.Description>{wf.description}</Card.Description>
					</Card.Header>
					
					<!-- <Card.Content class="pt-4 bg-slate-50/50"> -->
					<!-- 	<div class="space-y-3"> -->
					<!-- 		<div class="flex items-center text-sm"> -->
					<!-- 			<Play class="h-4 w-4 mr-2 text-blue-500" /> -->
					<!-- 			<span class="font-medium">Trigger:</span> -->
					<!-- 			<span class="ml-2 text-muted-foreground">{wf.trigger.type}</span> -->
					<!-- 		</div> -->
					<!-- 		<div class="flex items-center text-sm"> -->
					<!-- 			<Slack class="h-4 w-4 mr-2 text-orange-500" /> -->
					<!-- 			<span class="font-medium">Actions:</span> -->
					<!-- 			<span class="ml-2 text-muted-foreground">{wf.actions.length} steps</span> -->
					<!-- 		</div> -->
					<!-- 	</div> -->
					<!-- </Card.Content> -->

					<Card.Footer class="border-t bg-white p-3 flex justify-end gap-2">
						<Button variant="ghost" size="sm" class="text-destructive hover:bg-destructive/10">
							<Trash2 class="h-4 w-4" />
						</Button>
						<Button variant="outline" size="sm">Edit Config</Button>
					</Card.Footer>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
