<script lang="ts">
	import {
		SvelteFlow,
		Controls,
		Background,
		addEdge,
		useSvelteFlow,
		type Node
	} from '@xyflow/svelte';
	import ActionNode from './ActionNode.svelte';
	import TriggerNode from './TriggerNode.svelte';
	import ConditionNode from './ConditionNode.svelte';

	let { nodes = $bindable(), edges = $bindable(), onNodeClick } = $props();

	const nodeTypes: any = {
		trigger: TriggerNode,
		action: ActionNode,
		condition: ConditionNode
	};

	const { screenToFlowPosition } = useSvelteFlow();

	function onDragOver(event: DragEvent) {
		event.preventDefault();
		if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		const nodeType = (event.dataTransfer?.getData('application/reactflow-type') ||
			event.dataTransfer?.getData('application/svelteflow-type')) as 'trigger' | 'action' | 'condition';
		const catalogType =
			event.dataTransfer?.getData('application/reactflow-nodetype') ||
			event.dataTransfer?.getData('application/svelteflow-nodetype');

		if (!nodeType || !catalogType) return;

		const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
		const config: Record<string, any> = {};
		if (catalogType === 'label_email') {
			config.label_info = {
				name: '',
				color: { backgroundColor: '#ffffff', textColor: '#000000' }
			};
		}

		const newNode: Node = {
			id: `${nodeType}-${Date.now()}`,
			type: nodeType,
			position,
			data: { type: catalogType, config }
		};

		if (nodeType === 'trigger') {
			nodes = [newNode, ...nodes.filter((n: Node) => n.id !== 'trigger')];
		} else {
			nodes = [...nodes, newNode];
		}
	}
</script>

<div class="h-full w-full" ondragover={onDragOver} ondrop={onDrop} role="presentation">
	<SvelteFlow
		bind:nodes
		bind:edges
		{nodeTypes}
		onnodeclick={onNodeClick}
		onconnect={(params) => (edges = addEdge(params, edges))}
		fitView
	>
		<Controls />
		<Background gap={20} />
	</SvelteFlow>
</div>
