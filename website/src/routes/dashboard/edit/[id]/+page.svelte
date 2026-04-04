<script lang="ts">
	import { onMount } from 'svelte';
	import { type Node, type Edge, SvelteFlowProvider } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import { api } from '$lib/api/client';
	import { page } from '$app/state';
	import { Loader, Save, ChevronLeft, Rocket, LayoutDashboard } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import { goto } from '$app/navigation';
	import { toast, Toaster } from 'svelte-sonner';
	import { getLayoutedElements } from '$lib/utils/layout';
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

	function syncFlowState(config: WorkflowDef, uiMetadata?: any) {
		if (!config || !config.nodes) return;

		let newNodes: Node[] = [];
		let newEdges: Edge[] = [];

		if (uiMetadata && uiMetadata.nodes && uiMetadata.nodes.length > 0) {
			// Restore from UI metadata (positions preserved)
			newNodes = uiMetadata.nodes.map((uiNode: any) => {
				const backendNode = config.nodes[uiNode.id];
				return {
					...uiNode,
					type: backendNode?.type || uiNode.type,
					data: backendNode ? backendNode.config : uiNode.data
				};
			});
			newEdges = uiMetadata.edges || [];
		} else {
			// Generate from scratch from the backend nodes map
			newNodes = Object.entries(config.nodes).map(([id, node]) => ({
				id,
				type: node.type as any,
				data: node.config,
				position: { x: 0, y: 0 }
			}));

			newEdges = (config.edges || []).map((edge, index) => ({
				id: edge.id || `e-${index}`,
				source: edge.source,
				target: edge.target,
				sourceHandle: edge.sourceHandle || null,
				targetHandle: edge.targetHandle || null,
				animated: true
			}));
		}

		nodes = newNodes;
		edges = newEdges;

		// If no UI metadata, automatically apply layout
		if (!uiMetadata && nodes.length > 0) {
			setTimeout(() => onLayout('LR'), 50);
		}
	}

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

					syncFlowState(data);
					isLoading = false;
					return;
				}
			}

			const config: WorkflowDef = {
				name: 'New Custom Agent',
				description: 'Automate tasks with custom logic.',
				nodes: {
					trigger: {
						id: 'trigger',
						type: 'trigger',
						config: {
							type: 'manual',
							config: { description: 'Triggered manually via the UI' }
						}
					}
				},
				edges: [],
				start_node_ids: ['trigger']
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

			syncFlowState(config);
			isLoading = false;
			return;
		}

		try {
			const res = await api.get<Workflow>(`/api/workflow/get_workflow/${id}`);
			workflow = res;

			if (workflow) {
				syncFlowState(workflow.config, workflow.ui_metadata);
			}
		} catch (err: any) {
			toast.error('Failed to load workflow.');
			console.error('Failed to load workflow:', err);
		} finally {
			isLoading = false;
		}
	}

	function onLayout(direction = 'LR') {
		const layouted = getLayoutedElements(nodes, edges, direction);
		nodes = [...layouted.nodes];
		edges = [...layouted.edges];
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
					<Button
						variant="ghost"
						size="sm"
						class="gap-2"
						onclick={() => onLayout('LR')}
						disabled={isLoading}
					>
						<LayoutDashboard class="h-4 w-4" /> Layout
					</Button>

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
			<ConfigPanel bind:node={selectedNode} {nodes} onClose={() => (selectedNode = null)} />
		{/if}
	{:else if isLoading}
		<div class="flex h-full w-full items-center justify-center">
			<Loader class="animate-spin text-primary" size={48} />
		</div>
	{/if}
</div>
