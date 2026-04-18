<script lang="ts">
	import {
		SvelteFlow,
		Controls,
		Background,
		addEdge,
		useSvelteFlow,
		type Node,
		type Connection
	} from '@xyflow/svelte';
	import ActionNode from './ActionNode.svelte';
	import TriggerNode from './TriggerNode.svelte';
	import ConditionNode from './ConditionNode.svelte';

	let { nodes = $bindable(), edges = $bindable(), onNodeClick, takeSnapshot } = $props();

	const nodeTypes: any = {
		trigger: TriggerNode,
		action: ActionNode,
		condition: ConditionNode
	};

	const { screenToFlowPosition } = useSvelteFlow();

	function onDragOver(event: DragEvent) {
		event.preventDefault();
		if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
		takeSnapshot();
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		const nodeType = (event.dataTransfer?.getData('application/reactflow-type') ||
			event.dataTransfer?.getData('application/svelteflow-type')) as
			| 'trigger'
			| 'action'
			| 'condition';
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
			nodes = [newNode, ...nodes.filter((n: Node) => n.type !== 'trigger')];
		} else {
			nodes = [...nodes, newNode];
		}

		setTimeout(takeSnapshot, 0);
	}

	function onNodeDragStop() {
		takeSnapshot();
	}

	function onConnect(connection: Connection) {
		edges = addEdge({ ...connection, animated: true }, edges);
		setTimeout(takeSnapshot, 0);
	}

	function onEdgesChange(changes: any) {
		const isSignificant = changes.some((c: any) => c.type === 'remove' || c.type === 'reset');
		if (isSignificant) {
			setTimeout(takeSnapshot, 0);
		}
	}
</script>

<div class="h-full w-full" role="presentation">
	<SvelteFlow
		bind:nodes
		bind:edges
		{nodeTypes}
		onconnect={onConnect}
		onnodeclick={onNodeClick}
		onnodedragstop={onNodeDragStop}
		onedgeschange={onEdgesChange}
		ondragover={onDragOver}
		ondrop={onDrop}
		fitView
	>
		<Controls />
		<Background gap={20} />
	</SvelteFlow>
</div>
