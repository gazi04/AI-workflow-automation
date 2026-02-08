<script lang="ts">
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/api';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import * as Card from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import {
		Loader2,
		Sparkles,
		ArrowRight,
		CheckCircle2,
		AlertCircle,
		ChevronLeft
	} from 'lucide-svelte';
	import { goto } from '$app/navigation';

	type AIResponse = components['schemas']['AIResponse'];
	type WorkflowDef = components['schemas']['WorkflowDefinition'];

	let prompt = $state('');
	let isAnalyzing = $state(false);
	let generatedWorkflow = $state<WorkflowDef | null>(null);
	let errorMessage = $state('');

	const API_BASE_URL = 'http://localhost:8000';

	async function interpretCommand() {
		if (!prompt) return;

		isAnalyzing = true;
		errorMessage = '';
		generatedWorkflow = null;

		try {
      const result = await api.post<AIResponse>('/api/ai/interpret', { text: prompt });

			if (result.success && result.data) {
				generatedWorkflow = result.data;
			} else {
				errorMessage = result.error || 'AI could not structure that request.';
			}
		} catch (err) {
      errorMessage = err.message || 'Server connection lost. Please try again.';
      console.error('Interpretation error:', err);
		} finally {
			isAnalyzing = false;
		}
	}

	async function confirmAndDeploy() {
		// Logic to save the workflow would go here
		goto('/dashboard?created=success');
	}
</script>

<div class="min-h-screen bg-background p-6 lg:p-12">
	<div class="mx-auto max-w-5xl space-y-6">
		<div class="flex flex-col gap-4">
			<Button variant="ghost" size="sm" class="w-fit gap-2" onclick={() => goto('/dashboard')}>
				<ChevronLeft class="h-4 w-4" /> Back to Fleet
			</Button>
			<div>
				<h1 class="text-3xl font-bold tracking-tight">Create New Agent</h1>
				<p class="text-muted-foreground">
					Describe your automation goal and let AI handle the configuration.
				</p>
			</div>
		</div>

		<div class="grid items-start gap-8 lg:grid-cols-2">
			<section class="space-y-4">
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-lg">Instructions</Card.Title>
						<Card.Description>What should this agent do for you?</Card.Description>
					</Card.Header>
					<Card.Content>
						<Textarea
							placeholder="e.g., When I get an email about a new lead, add it to my sheet and send a Slack notification."
							class="min-h-[200px] text-base"
							bind:value={prompt}
						/>
					</Card.Content>
					<Card.Footer>
						<Button class="w-full" disabled={isAnalyzing || !prompt} onclick={interpretCommand}>
							{#if isAnalyzing}
								<Loader2 class="mr-2 h-4 w-4 animate-spin" /> Analyzing...
							{:else}
								Interpret with AI <Sparkles class="ml-2 h-4 w-4" />
							{/if}
						</Button>
					</Card.Footer>
				</Card.Root>

				{#if errorMessage}
					<div
						class="flex items-center gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
					>
						<AlertCircle class="h-4 w-4" />
						{errorMessage}
					</div>
				{/if}
			</section>

			<section>
				{#if generatedWorkflow}
					<Card.Root class="animate-in fade-in slide-in-from-bottom-2">
						<Card.Header>
							<div class="flex items-center justify-between">
								<Badge variant="outline" class="border-primary/20 bg-primary/5 text-primary"
									>Preview</Badge
								>
								<CheckCircle2 class="h-5 w-5 text-primary" />
							</div>
							<Card.Title class="pt-2 text-2xl">{generatedWorkflow.name}</Card.Title>
							<Card.Description>{generatedWorkflow.description}</Card.Description>
						</Card.Header>
						<Card.Content class="space-y-6">
							<div class="space-y-2">
								<h4 class="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
									Trigger
								</h4>
								<div class="flex items-center gap-3 rounded-md border bg-muted/50 p-3">
									<div
										class="flex h-8 w-8 items-center justify-center rounded border bg-background font-mono text-xs shadow-sm"
									>
										T
									</div>
									<span class="font-medium capitalize"
										>{generatedWorkflow.trigger.type.replace('_', ' ')}</span
									>
								</div>
							</div>

							<div class="space-y-2">
								<h4 class="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
									Actions
								</h4>
								<div class="space-y-2">
									{#each generatedWorkflow.actions as action, i}
										<div class="flex items-center gap-3 rounded-md border p-3">
											<div
												class="flex h-8 w-8 items-center justify-center rounded bg-primary font-mono text-xs text-primary-foreground"
											>
												{i + 1}
											</div>
											<span class="font-medium capitalize">{action.type.replace('_', ' ')}</span>
										</div>
									{/each}
								</div>
							</div>
						</Card.Content>
						<Card.Footer>
							<Button onclick={confirmAndDeploy} class="w-full">Confirm and Deploy Agent</Button>
						</Card.Footer>
					</Card.Root>
				{:else}
					<div
						class="flex h-[400px] flex-col items-center justify-center rounded-xl border border-dashed text-center"
					>
						<div class="mb-4 rounded-full bg-muted p-4">
							<Sparkles class="h-8 w-8 text-muted-foreground/50" />
						</div>
						<p class="text-sm text-muted-foreground">The agent's blueprint will appear here.</p>
					</div>
				{/if}
			</section>
		</div>
	</div>
</div>
