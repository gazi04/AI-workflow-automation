<script lang="ts">
	import { onMount } from 'svelte';
	import { SvelteFlow, Controls, Background, type Node, type Edge } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import { api } from '$lib/api/client';
	import { page } from '$app/state';
	import { Loader2, Save, X } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import TriggerNode from '$lib/components/editor/TriggerNode.svelte';
	import ActionNode from '$lib/components/editor/ActionNode.svelte';
	import ConfigPanel from '$lib/components/editor/ConfigPanel.svelte';

	let isLoading = $state(true);
	let workflow = $state<any>(null);
	let nodes = $state<Node[]>([]);
	let edges = $state<Edge[]>([]);
	let selectedNode = $state<Node | null>(null);

	const nodeTypes = {
		trigger: TriggerNode,
		action: ActionNode
	};

	async function loadWorkflow() {
		try {
			const id = page.params.id;
			const res = await api.get<any>(`/api/workflow/get_workflows`);
			workflow = res.find((w: any) => w.id === id);

			if (workflow) {
				// IMPORTANT: If we have UI metadata, use it. Otherwise, auto-layout.
				if (workflow.ui_metadata && workflow.ui_metadata.nodes.length > 0) {
					nodes = workflow.ui_metadata.nodes;
					edges = workflow.ui_metadata.edges;
				} else {
					generateFlow(workflow.config);
				}
			}
		} finally {
			isLoading = false;
		}
	}

	function generateFlow(config: any) {
		// ... (Your existing generateFlow logic, but use types: 'trigger' and 'action')
		// Ensure you add 'type: "trigger"' and 'type: "action"' to the objects
		nodes = [
			{ id: 'trigger', type: 'trigger', data: { ...config.trigger }, position: { x: 0, y: 0 } },
			...config.actions.map((a, i) => ({
				id: `action-${i}`,
				type: 'action',
				data: { ...a },
				position: { x: (i + 1) * 300, y: 0 }
			}))
		];
		// ... generate edges as you did before
	}

	function onNodeClick({ detail }: any) {
		selectedNode = detail.node;
	}

	async function handleSave() {
		try {
			isLoading = true;
			// We send the current state of nodes/edges as ui_metadata
			const updatedConfig = {
				...workflow.config,
				ui_metadata: { nodes, edges }
			};

			await api.patch(`/api/workflow/update-config`, {
				deployment_id: workflow.id, // Or deployment_id
				config: updatedConfig
			});
			alert('Workflow saved successfully!');
		} catch (e) {
			console.error(e);
		} finally {
			isLoading = false;
		}
	}

	onMount(loadWorkflow);
</script>

<div class="flex h-screen overflow-hidden bg-background">
	<div class="flex flex-grow flex-col">
		<header class="flex items-center justify-between border-b bg-card p-4">
			<div>
				<h1 class="text-lg font-bold">{workflow?.name || 'Loading...'}</h1>
			</div>
			<Button onclick={handleSave} size="sm" class="gap-2" disabled={isLoading}>
				{#if isLoading}<Loader2 class="animate-spin" size={16} />{/if}
				<Save class="h-4 w-4" /> Save
			</Button>
		</header>

		<main class="relative flex-grow">
			<SvelteFlow {nodes} {edges} {nodeTypes} onnodeclick={onNodeClick} fitView>
				<Controls />
				<Background color="#eee" gap={20} />
			</SvelteFlow>
		</main>
	</div>

	{#if selectedNode}
		<ConfigPanel bind:node={selectedNode} onClose={() => (selectedNode = null)} />
	{/if}
</div>
