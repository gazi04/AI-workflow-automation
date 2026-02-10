<script lang="ts">
    import { onMount } from 'svelte';
    import { SvelteFlow, Controls, Background, type Node, type Edge } from '@xyflow/svelte';
    import '@xyflow/svelte/dist/style.css';
    import { api } from '$lib/api/client';
    import { page } from '$app/state';
    import { Loader2, Save } from 'lucide-svelte';
    import { Button } from '$lib/components/ui/button';

    let isLoading = $state(true);
    let nodes = $state<Node[]>([]);
    let edges = $state<Edge[]>([]);

    async function loadWorkflow() {
        try {
            const id = page.params.id;
            const wf = await api.get<any>(`/api/workflow/get_workflows`);
            const currentWf = wf.find((w: any) => w.deployment_id === id);

            if (currentWf) {
                generateFlow(currentWf.config);
            }
        } finally {
            isLoading = false;
        }
    }

    function generateFlow(config: any) {
        const newNodes: Node[] = [];
        const newEdges: Edge[] = [];

        newNodes.push({
            id: 'trigger',
            type: 'default',
            data: { label: `⚡ TRIGGER: ${config.trigger.type}` },
            position: { x: 0, y: 0 },
            style: 'background: #f0f9ff; border: 2px solid #0ea5e9; border-radius: 8px; padding: 10px;'
        });

        config.actions.forEach((action: any, index: number) => {
            const nodeId = `action-${index}`;
            newNodes.push({
                id: nodeId,
                type: 'default',
                data: { label: `⚙️ ACTION: ${action.type}` },
                position: { x: (index + 1) * 250, y: 0 },
                style: 'background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;'
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

    async function handleSave() {
        console.log("Saving current layout...");
    }

    onMount(loadWorkflow);
</script>

<div class="flex flex-col h-screen bg-background">
    <header class="p-4 border-b flex justify-between items-center bg-card text-card-foreground">
        <div>
            <h1 class="font-bold text-lg">Workflow Editor</h1>
            <p class="text-xs text-muted-foreground">ID: {page.params.id}</p>
        </div>
        <Button onclick={handleSave} size="sm" class="gap-2">
            <Save class="h-4 w-4" /> Save Changes
        </Button>
    </header>

    <main class="flex-grow relative">
        {#if isLoading}
            <div class="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
                <Loader2 class="h-8 w-8 animate-spin" />
            </div>
        {/if}

        <SvelteFlow 
            bind:nodes 
            bind:edges 
            fitView
        >
            <Controls />
            <Background color="#ccc" gap={20} />
        </SvelteFlow>
    </main>
</div>

<style>
    /* Ensure the container has height */
    :global(.svelte-flow) {
        background: var(--background);
    }
</style>
