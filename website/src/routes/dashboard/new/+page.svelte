<script lang="ts">
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import * as Card from '$lib/components/ui/card';
	import {
		Pencil,
		Loader,
		Sparkles,
		CircleAlert,
		ChevronLeft,
	} from 'lucide-svelte';
	import { goto } from '$app/navigation';

	type AIResponse = components['schemas']['AIResponse'];
	type WorkflowDef = components['schemas']['WorkflowDefinition-Output'];

	let prompt = $state('');
	let isAnalyzing = $state(false);
	let isDeployed = $state(false);
	let generatedWorkflow = $state<WorkflowDef | null>(null);
	let errorMessage = $state('');

	async function interpretCommand() {
		if (!prompt) return;

		isAnalyzing = true;
		errorMessage = '';
		generatedWorkflow = null;

		try {
			const result = await api.post<AIResponse>('/api/ai/interpret', { text: prompt });

			if (result.success && result.data) {
				sessionStorage.setItem('ai_blueprint', JSON.stringify(result.data));
				goto('/dashboard/edit/new?source=ai');
			} else {
				errorMessage = result.error || 'AI could not structure that request.';
			}
		} catch (err: any) {
			errorMessage = err.message || 'Server connection lost. Please try again.';
		} finally {
			isAnalyzing = false;
		}
	}
</script>

<div class="min-h-screen bg-background p-6 lg:p-12">
	<div class="mx-auto max-w-5xl space-y-6">
		<div class="flex flex-col gap-4">
			<div class="flex flex-row justify-between">
				<Button variant="ghost" size="sm" class="w-fit gap-2" onclick={() => goto('/dashboard')}>
					<ChevronLeft class="h-4 w-4" /> Back to Fleet
				</Button>
				<Button
					variant="outline"
					class="w-fit gap-2"
					disabled={isAnalyzing || isDeployed}
					onclick={() => goto('/dashboard/edit/new')}
				>
					<Pencil class="h-4 w-4" /> Design from Scratch
				</Button>
			</div>

			<div>
				<h1 class="text-3xl font-bold tracking-tight">Create New Agent</h1>
				<p class="text-muted-foreground">
					Describe your automation goal. AI will build and deploy it instantly.
				</p>
			</div>
      <section class="space-y-4">
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-lg">Instructions</Card.Title>
						<Card.Description>What should this agent do?</Card.Description>
					</Card.Header>
					<Card.Content>
						<Textarea
							placeholder="e.g., When I get an email about a new lead, add it to my sheet..."
							class="min-h-50 text-base"
							bind:value={prompt}
							disabled={isAnalyzing || isDeployed}
						/>
					</Card.Content>
					<Card.Footer>
						<Button
							class="w-full"
							disabled={isAnalyzing || !prompt || isDeployed}
							onclick={interpretCommand}
						>
							{#if isAnalyzing}
								<Loader class="mr-2 h-4 w-4 animate-spin" /> Generating Agent...
							{:else}
								Generate Blueprint <Sparkles class="ml-2 h-4 w-4" />
							{/if}
						</Button>
					</Card.Footer>
				</Card.Root>

				{#if errorMessage}
					<div
						class="flex items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
					>
						<CircleAlert class="h-4 w-4" />
						{errorMessage}
					</div>
				{/if}
			</section>
		</div>
	</div>
</div>
