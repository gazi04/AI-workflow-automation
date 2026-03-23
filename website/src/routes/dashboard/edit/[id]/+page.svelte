<script lang="ts">
	import { onMount } from 'svelte';
	import { type Node, type Edge, SvelteFlowProvider } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import { api } from '$lib/api/client';
	import { page } from '$app/state';
	import { Loader, Save, ChevronLeft, Rocket } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import { goto } from '$app/navigation';
	import { toast, Toaster } from 'svelte-sonner';
	import ConfigPanel from '$lib/components/editor/ConfigPanel.svelte';
	import Sidebar from '$lib/components/editor/Sidebar.svelte';
	import FlowCanvas from '$lib/components/editor/FlowCanvas.svelte';
	import type { components } from '$lib/types/schema';

	type WorkflowDef = components['schemas']['WorkflowDefinition-Output'];

	type Workflow = {
		id: string;
		deployment_id: string;
		is_active: boolean;
		name: string;
		description: string;
		config: WorkflowDef;
		ui_metadata?: { nodes: Node[]; edges: Edge[] } | null;
	};

	let isLoading = $state(true);

	let workflow = $state<Workflow | null>(null);
	let nodes = $state<Node[]>([]);
	let edges = $state<Edge[]>([]);
	let selectedNode = $state<Node | null>(null);

	async function loadWorkflow() {
		const id = page.params.id;
		const source = page.url.searchParams.get('source');

		if (id === 'new') {
			if (source === 'ai') {
				const blueprint = sessionStorage.getItem('ai_blueprint');
				if (blueprint) {
					const data: WorkflowDef = JSON.parse(blueprint);
					workflow = {
						id: 'new',
						deployment_id: '',
						is_active: false,
						name: data.name || 'AI Generated Agent',
						description: data.description || '',
						config: data,
						ui_metadata: null
					} as Workflow;
 
					if (data.nodes) {
						// Transform new schema Nodes Map to SvelteFlow Node[]
						const newNodes: Node[] = [];
						Object.entries(data.nodes).forEach(([id, node], index) => {
							newNodes.push({
								id,
								type: node.type as 'trigger' | 'action',
								data: node.config,
								position: { x: index * 350, y: 0 }
							});
						});
						nodes = newNodes;
						edges = data.edges || [];
					} else {
						// Fallback for legacy format if any
						generateFlow(data);
					}
					isLoading = false;
					return;
				}
			}

			const config: WorkflowDef = {
				name: 'New Custom Agent',
				description: 'Automate tasks with custom logic.',
				nodes: {},
				edges: [],
				start_node_ids: []
			};
 
			workflow = {
				id: 'new',
				deployment_id: '',
				is_active: false,
				name: config.name,
				description: config.description,
				config: config,
				ui_metadata: null
			} as Workflow;
 
			generateFlow({
				trigger: { type: 'manual', config: { description: 'Triggered manually via the UI' } },
				actions: []
			});
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
					// Use saved UI positions but sync with latest config data
					nodes = workflow.ui_metadata.nodes.map((uiNode) => {
						const backendNode = workflow?.config.nodes[uiNode.id];
						return {
							...uiNode,
							data: backendNode ? backendNode.config : uiNode.data
						};
					});
					edges = workflow.ui_metadata.edges;
				} else if (workflow.config && workflow.config.nodes) {
					// New schema structure without UI metadata or fallback
					const newNodes: Node[] = [];
					const workflowNodes = workflow.config.nodes;
 
					Object.entries(workflowNodes).forEach(([id, node], index) => {
						newNodes.push({
							id,
							type: node.type as 'trigger' | 'action',
							data: node.config,
							position: { x: index * 350, y: 0 }
						});
					});
 
					nodes = newNodes;
					edges = workflow.config.edges || [];
				} else if (workflow.config) {
					generateFlow(workflow.config);
				}
			}
		} catch (err: any) {
			toast.error('Failed to load workflow.');
			console.error('Failed to load workflow:', err);
		} finally {
			isLoading = false;
		}
	}

	function generateFlow(config: any) {
		const newNodes: Node[] = [];
		if (config.trigger) {
			newNodes.push({
				id: 'trigger',
				type: 'trigger',
				data: { type: config.trigger.type, config: config.trigger.config },
				position: { x: 0, y: 0 }
			});
		}

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

	function getUpdatedConfig(): WorkflowDef | null {
		if (!workflow) return null;

		const currentNodes = $state.snapshot(nodes);
		const currentEdges = $state.snapshot(edges);

		const nodesDict: Record<string, components['schemas']['WorkflowNode-Input']> = {};
		const startNodeIds: string[] = [];

		currentNodes.forEach((node) => {
			nodesDict[node.id] = {
				id: node.id,
				type: node.type as 'trigger' | 'action' | 'condition',
				config: node.data as any
			};

			if (node.type === 'trigger') {
				startNodeIds.push(node.id);
			}
		});

		if (startNodeIds.length === 0) {
			toast.error('Workflow must have at least one trigger!');
			return null;
		}

		return {
			name: workflow.name,
			description: workflow.description,
			nodes: nodesDict,
			edges: currentEdges.map((e) => ({
				id: e.id,
				source: e.source,
				target: e.target,
				sourceHandle: e.sourceHandle,
				targetHandle: e.targetHandle
			})),
			start_node_ids: startNodeIds,
			ui_metadata: {
				nodes: currentNodes,
				edges: currentEdges
			}
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

				toast.success('Workflow deployed successfully!');
				goto(`/dashboard/edit/${res.id}`);
			} else {
				await api.patch(`/api/workflow/update-config`, {
					deployment_id: workflow.id,
					config: config
				});
				toast.success('Workflow saved successfully!');
			}
		} catch (e) {
			toast.error('Failed to save the workflow.');
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
