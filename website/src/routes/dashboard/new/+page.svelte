<script lang="ts">
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import * as Card from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Loader2, Sparkles, CheckCircle2, AlertCircle, ChevronLeft, Rocket } from 'lucide-svelte';
	import { goto } from '$app/navigation';

	type AIResponse = components['schemas']['AIResponse'];
	type WorkflowDef = components['schemas']['WorkflowDefinition-Output'];

	let prompt = $state('');
	let isAnalyzing = $state(false);
	let isDeployed = $state(false);
	let generatedWorkflow = $state<WorkflowDef | null>(null);
	let errorMessage = $state('');

	async function interpretAndDeploy() {
		if (!prompt) return;

		isAnalyzing = true;
		errorMessage = '';
		generatedWorkflow = null;

		try {
			const result = await api.post<AIResponse>('/api/ai/interpret', { text: prompt });

			if (result.success && result.data) {
				generatedWorkflow = result.data;
				isDeployed = true;

				setTimeout(() => {
					goto('/dashboard?created=success');
				}, 2500);
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
			<Button variant="ghost" size="sm" class="w-fit gap-2" onclick={() => goto('/dashboard')}>
				<ChevronLeft class="h-4 w-4" /> Back to Fleet
			</Button>
			<div>
				<h1 class="text-3xl font-bold tracking-tight">Create New Agent</h1>
				<p class="text-muted-foreground">
					Describe your automation goal. AI will build and deploy it instantly.
				</p>
			</div>
		</div>

		<div class="grid items-start gap-8 lg:grid-cols-2">
			<section class="space-y-4">
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-lg">Instructions</Card.Title>
						<Card.Description>What should this agent do?</Card.Description>
					</Card.Header>
					<Card.Content>
						<Textarea
							placeholder="e.g., When I get an email about a new lead, add it to my sheet..."
							class="min-h-[200px] text-base"
							bind:value={prompt}
							disabled={isAnalyzing || isDeployed}
						/>
					</Card.Content>
					<Card.Footer>
						<Button
							class="w-full"
							disabled={isAnalyzing || !prompt || isDeployed}
							onclick={interpretAndDeploy}
						>
							{#if isAnalyzing}
								<Loader2 class="mr-2 h-4 w-4 animate-spin" /> Deploying Agent...
							{:else if isDeployed}
								<CheckCircle2 class="mr-2 h-4 w-4" /> Agent Active!
							{:else}
								Deploy with AI <Sparkles class="ml-2 h-4 w-4" />
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
				{#if isDeployed && generatedWorkflow}
					<Card.Root class="animate-in border-primary/50 bg-primary/5 duration-500 zoom-in-95">
						<Card.Header class="text-center">
							<div
								class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground"
							>
								<Rocket class="h-6 w-6" />
							</div>
							<Card.Title class="text-2xl">Agent Deployed!</Card.Title>
							<Card.Description>
								<strong>{generatedWorkflow.name}</strong> is now monitoring your workspace.
							</Card.Description>
						</Card.Header>
						<Card.Content>
							<div class="space-y-4 rounded-lg border bg-background p-4">
								<div class="flex items-center gap-2 text-sm font-medium">
									<Badge>Active</Badge>
									<span class="text-muted-foreground"
										>Trigger: {generatedWorkflow.trigger.type}</span
									>
								</div>
								<p class="text-sm text-muted-foreground italic">
									"{generatedWorkflow.description}"
								</p>
							</div>
							<p class="mt-4 animate-pulse text-center text-xs text-muted-foreground">
								Redirecting to Control Center...
							</p>
						</Card.Content>
					</Card.Root>
				{:else if isAnalyzing}
					<div
						class="flex h-[400px] flex-col items-center justify-center rounded-xl border border-dashed text-center"
					>
						<Loader2 class="mb-4 h-8 w-8 animate-spin text-primary" />
						<p class="text-sm font-medium">AI is architecting your workflow...</p>
						<p class="text-xs text-muted-foreground">Provisioning triggers and actions.</p>
					</div>
				{:else}
					<div
						class="flex h-[400px] flex-col items-center justify-center rounded-xl border border-dashed text-center"
					>
						<div class="mb-4 rounded-full bg-muted p-4">
							<Sparkles class="h-8 w-8 text-muted-foreground/50" />
						</div>
						<p class="text-sm text-muted-foreground">
							Your agent's blueprint will appear here after deployment.
						</p>
					</div>
				{/if}
			</section>
		</div>
	</div>
</div>
