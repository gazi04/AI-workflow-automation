<script lang="ts">
	import { SvelteFlow, type Node, type Edge, addEdge } from '@xyflow/svelte';
	import { api } from '$lib/api/client';
	import TriggerNode from './TriggerNode.svelte';
	import ActionNode from './ActionNode.svelte';

	let { workflow } = $props(); // The object from your API

	// 1. Define Node Types
	const nodeTypes = {
		trigger: TriggerNode,
		action: ActionNode
	};

	// 2. Initial State: If DB has ui_metadata, use it. Otherwise, auto-layout.
	let nodes = $state<Node[]>(workflow.ui_metadata?.nodes || autoLayoutNodes(workflow));
	let edges = $state<Edge[]>(workflow.ui_metadata?.edges || autoLayoutEdges(workflow));

	function onConnect(params) {
		edges = addEdge(params, edges);
	}

	// 3. Save Logic
	async function saveWorkflow() {
		const ui_metadata = { nodes, edges };
		// This goes to your PATCH /api/workflow/update-config
		await api.patch(`/api/workflow/update-config`, {
			deployment_id: workflow.deployment_id,
			config: {
				...workflow.config,
				ui_metadata // The backend translator handles the rest!
			}
		});
	}
</script>

<div class="h-full w-full">
	<SvelteFlow {nodes} {edges} {nodeTypes} onconnect={onConnect} fitView>
		<Background variant="dots" />
		<Controls />
	</SvelteFlow>
</div>
