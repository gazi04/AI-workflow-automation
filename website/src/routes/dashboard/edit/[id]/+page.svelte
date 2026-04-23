<script lang="ts">
	import { onMount } from 'svelte';
	import { type Node, type Edge, SvelteFlowProvider } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import { api } from '$lib/api/client';
	import { page } from '$app/state';
	import { Loader, Save, ChevronLeft, Rocket, LayoutDashboard, Undo2, Redo2 } from 'lucide-svelte';
	import { Button } from '$lib/components/ui/button';
	import { goto } from '$app/navigation';
	import { toast, Toaster } from 'svelte-sonner';
	import { getLayoutedElements } from '$lib/utils/layout';
	import { HistoryManager } from '$lib/utils/history.svelte';
  import AIAgentChat from '$lib/components/editor/AIAgentChat.svelte';
	import ConfigPanel from '$lib/components/editor/ConfigPanel.svelte';
	import Sidebar from '$lib/components/editor/Sidebar.svelte';
	import FlowCanvas from '$lib/components/editor/FlowCanvas.svelte';
	import type { components } from '$lib/types/schema';

	const history = new HistoryManager<{ nodes: Node[]; edges: Edge[] }>();

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
			setTimeout(takeSnapshot, 100);
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
		takeSnapshot();
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

				workflow.id = res.id;
				toast.success('Workflow deployed successfully!');
				goto(`/dashboard/edit/${res.id}`);
			} else {
				await api.patch(`/api/workflow/update-config`, {
					deployment_id: workflow.id,
					config: config
				});
				toast.success('Workflow saved successfully!');
			}
		} catch (e: any) {
			let message = 'Failed to save the workflow.';

			if (e.detail && Array.isArray(e.detail) && e.detail.length > 0) {
				message = e.detail[0].msg;
				// Pydantic/FastAPI often prefix ValueError messages with 'Value error, '
				if (message.startsWith('Value error, ')) {
					message = message.replace('Value error, ', '');
				}
			} else if (e.message) {
				message = e.message;
			}

			toast.error(message);
			console.error('Save error:', e);
		} finally {
			isLoading = false;
		}
	}

	function takeSnapshot() {
		history.push({
			nodes: $state.snapshot(nodes),
			edges: $state.snapshot(edges)
		});
	}

	function handleUndo() {
		const previous = history.undo({ nodes, edges });
		if (previous) {
			nodes = previous.nodes;
			edges = previous.edges;
		}
	}

	function handleRedo() {
		const next = history.redo();
		if (next) {
			nodes = next.nodes;
			edges = next.edges;
		}
	}

	function handleKeyDown(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
			e.preventDefault();
			if (e.shiftKey) handleRedo();
			else handleUndo();
		}
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
			e.preventDefault();
			handleRedo();
		}
		if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNode) {
			if (
				document.activeElement?.tagName !== 'INPUT' &&
				document.activeElement?.tagName !== 'TEXTAREA'
			) {
				e.preventDefault();
				deleteSelectedNode();
			}
		}
	}

	function deleteSelectedNode() {
		if (!selectedNode) return;
		takeSnapshot();
		const nodeId = selectedNode.id;
		nodes = nodes.filter((n) => n.id !== nodeId);
		edges = edges.filter((e) => e.source !== nodeId && e.target !== nodeId);
		selectedNode = null;
	}

  function handleAIUpdate(newConfig: WorkflowDef) {
    // Sync the new backend schema to your SvelteFlow nodes/edges
    syncFlowState(newConfig, newConfig.ui_metadata);

    // Auto-layout the graph because the AI doesn't output X/Y coordinates
    setTimeout(() => {
      onLayout('LR');
      // Take a snapshot so the user can Undo the AI's changes if they don't like them
      takeSnapshot();
      toast.success("Workflow updated by AI");
    }, 100);
  }

	onMount(loadWorkflow);
</script>

<svelte:window onkeydown={handleKeyDown} />

<div class="flex h-screen overflow-hidden bg-background">
	{#if workflow}
		<Sidebar />

		<div class="flex grow flex-col">
			<header class="flex items-center justify-between border-b bg-card p-4">
				<div class="flex items-center gap-2">
					<Button variant="ghost" size="sm" onclick={() => goto('/dashboard')}>
						<ChevronLeft class="h-4 w-4" />
					</Button>

					<div class="ml-2 flex items-center gap-1 border-l pl-2">
						<Button
							variant="ghost"
							size="icon"
							class="h-8 w-8"
							onclick={handleUndo}
							disabled={!history.canUndo}
						>
							<Undo2 class="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="icon"
							class="h-8 w-8"
							onclick={handleRedo}
							disabled={!history.canRedo}
						>
							<Redo2 class="h-4 w-4" />
						</Button>
					</div>
				</div>

				<div class="flex flex-col items-center">
					<input
						type="text"
						bind:value={workflow.name}
						class="rounded bg-transparent px-2 text-center text-lg font-bold outline-none focus:ring-1 focus:ring-primary"
					/>
					<input
						type="text"
						bind:value={workflow.description}
						maxlength="100"
						class="w-full max-w-lg truncate bg-transparent text-center text-xs text-muted-foreground outline-none"
						title={workflow.description}
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
          <FlowCanvas bind:nodes bind:edges {onNodeClick} {takeSnapshot} />
        </SvelteFlowProvider>

        <AIAgentChat 
          onAIUpdate={handleAIUpdate} 
          getCurrentConfig={getUpdatedConfig} 
        />
      </main>
		</div>

		{#if selectedNode}
			<ConfigPanel
				bind:node={selectedNode}
				{nodes}
				onClose={() => (selectedNode = null)}
				onDelete={deleteSelectedNode}
			/>
		{/if}
	{:else if isLoading}
		<div class="flex h-full w-full items-center justify-center">
			<Loader class="animate-spin text-primary" size={48} />
		</div>
	{/if}
</div>
