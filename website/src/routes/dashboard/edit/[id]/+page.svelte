<script lang="ts">
	import { onMount } from 'svelte';
	import {
		SvelteFlow,
		Controls,
		Background,
		type Node,
		type Edge,
		useSvelteFlow,
		SvelteFlowProvider,
		addEdge
	} from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import { api } from '$lib/api/client';
	import { page } from '$app/state';
	import { Loader, Save, ChevronLeft, Rocket } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import { goto } from '$app/navigation';
	import TriggerNode from '$lib/components/editor/TriggerNode.svelte';
	import ActionNode from '$lib/components/editor/ActionNode.svelte';
	import ConfigPanel from '$lib/components/editor/ConfigPanel.svelte';
	import Sidebar from '$lib/components/editor/Sidebar.svelte';
	import FlowCanvas from '$lib/components/editor/FlowCanvas.svelte';
	import type { components } from '$lib/types/schema';

	type WorkflowDef = components['schemas']['WorkflowDefinition-Output'];

	type Workflow = WorkflowDef & {
		deployment_id: string;
		id: string;
		is_active: boolean;
		name: string;
		config: any;
		ui_metadata?: { nodes: Node[]; edges: Edge[] } | null;
	};

	let isLoading = $state(true);

	let workflow = $state<Workflow | null>(null);
	let nodes = $state<Node[]>([]);
	let edges = $state<Edge[]>([]);
	let selectedNode = $state<Node | null>(null);

	const nodeTypes = {
		trigger: TriggerNode,
		action: ActionNode
	};

	async function loadWorkflow() {
		const id = page.params.id;
		const source = page.url.searchParams.get('source');

		if (id === 'new') {
			if (source === 'ai') {
				const blueprint = sessionStorage.getItem('ai_blueprint');
				if (blueprint) {
					const data = JSON.parse(blueprint);
					workflow = {
						id: 'new',
						deployment_id: '',
						is_active: false,
						name: data.name || 'AI Generated Agent',
						description: data.description || '',
						config: {
							trigger: data.trigger,
							actions: data.actions
						},
						ui_metadata: null
					} as Workflow;
					generateFlow(workflow.config);
					isLoading = false;
					return;
				}
			}

			workflow = {
				id: 'new',
				deployment_id: '',
				is_active: false,
				name: 'New Custom Agent',
				description: 'Automate tasks with custom logic.',
				config: {
					trigger: { type: 'manual', config: { description: 'Triggered manually via the UI' } },
					actions: []
				},
				ui_metadata: null
			} as Workflow;
			generateFlow(workflow.config);
			isLoading = false;
			return;
		}

		try {
			const res = await api.get<Workflow>(`/api/workflow/get_workflow/${id}`);
			workflow = res;

			if (workflow) {
				if (
					workflow.ui_metadata &&
					workflow.ui_metadata.nodes &&
					workflow.ui_metadata.nodes.length > 0
				) {
					nodes = workflow.ui_metadata.nodes;
					edges = workflow.ui_metadata.edges;
				} else if (workflow.config) {
					generateFlow(workflow.config);
				}
			}
		} catch (err: any) {
			console.error('Failed to load workflow:', err);
		} finally {
			isLoading = false;
		}
	}

	function generateFlow(config: any) {
		const newNodes: Node[] = [
			{
				id: 'trigger',
				type: 'trigger',
				data: { type: config.trigger.type, config: config.trigger.config },
				position: { x: 0, y: 0 }
			}
		];

		const newEdges: Edge[] = [];

		config.actions.forEach((action: any, index: number) => {
			const nodeId = `action-${index}`;
			newNodes.push({
				id: nodeId,
				type: 'action',
				data: { type: action.type, config: action.config },
				position: { x: (index + 1) * 350, y: 0 }
			});

			newEdges.push({
				id: `e-${index}`,
				source: index === 0 ? 'trigger' : `action-${index - 1}`,
				target: nodeId,
				animated: true
			});
		});

		nodes = newNodes;
		edges = newEdges;
	}

	function onNodeClick({ event, node }: { event: MouseEvent | TouchEvent; node: Node }) {
		selectedNode = node;
	}

	function getUpdatedConfig() {
		if (!workflow) return null;

		const triggerNode = nodes.find((n) => n.id === 'trigger' || n.type === 'trigger');
		const actionNodes = nodes
			.filter((n) => n.type === 'action')
			.sort((a, b) => a.position.x - b.position.x);

		if (!triggerNode) {
			alert('Workflow must have a trigger!');
			return null;
		}

		return {
			name: workflow.name,
			description: workflow.description,
			trigger: {
				type: triggerNode.data.type,
				config: triggerNode.data.config
			},
			actions: actionNodes.map((n) => ({
				type: n.data.type,
				config: n.data.config
			})),
			ui_metadata: { nodes, edges }
		};
	}

	async function handleSave() {
		const config = getUpdatedConfig();
		if (!config || !workflow) return;

		try {
			isLoading = true;

			if (workflow.id === 'new') {
				const res = await api.post<Workflow>(`/api/workflow/create`, {
					name: workflow.name,
					description: workflow.description,
					workflow_definition: config
				});

				sessionStorage.removeItem('ai_blueprint');

				alert('Workflow deployed successfully!');
				goto(`/dashboard/edit/${res.id}`);
			} else {
				await api.patch(`/api/workflow/update-config`, {
					deployment_id: workflow.id,
					config: config
				});
				alert('Workflow saved successfully!');
			}
		} catch (e) {
			console.error(e);
		} finally {
			isLoading = false;
		}
	}

	onMount(loadWorkflow);
</script>

<div class="flex h-screen overflow-hidden bg-background">
	{#if workflow}
		<Sidebar />

		<div class="flex grow flex-col">
			<header class="flex items-center justify-between border-b bg-card p-4">
				<Button variant="ghost" size="sm" class="w-fit gap-2" onclick={() => goto('/dashboard')}>
					<ChevronLeft class="h-4 w-4" /> Go to dashboard
				</Button>

				<div class="flex flex-col items-center">
					<input
						type="text"
						bind:value={workflow.name}
						class="rounded bg-transparent px-2 text-center text-lg font-bold outline-none focus:ring-1 focus:ring-primary"
					/>
					<input
						type="text"
						bind:value={workflow.description}
						class="bg-transparent text-center text-xs text-muted-foreground outline-none"
					/>
				</div>

				<div class="flex items-center gap-2">
					{#if workflow.id === 'new'}
						<Button
							onclick={handleSave}
							size="sm"
							class="gap-2"
							variant="default"
							disabled={isLoading}
						>
							{#if isLoading}<Loader class="animate-spin" size={16} />{/if}
							<Rocket class="h-4 w-4" /> Deploy
						</Button>
					{:else}
						<Button
							onclick={handleSave}
							size="sm"
							class="gap-2"
							variant="outline"
							disabled={isLoading}
						>
							{#if isLoading}<Loader class="animate-spin" size={16} />{/if}
							<Save class="h-4 w-4" /> Save
						</Button>
					{/if}
				</div>
			</header>

			<main class="relative grow">
				<SvelteFlowProvider>
					<FlowCanvas bind:nodes bind:edges {onNodeClick} />
				</SvelteFlowProvider>
			</main>
		</div>

		{#if selectedNode}
			<ConfigPanel bind:node={selectedNode} onClose={() => (selectedNode = null)} />
		{/if}
	{:else if isLoading}
		<div class="flex h-full w-full items-center justify-center">
			<Loader class="animate-spin text-primary" size={48} />
		</div>
	{/if}
</div>
