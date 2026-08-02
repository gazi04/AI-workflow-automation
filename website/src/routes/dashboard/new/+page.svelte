<script lang="ts">
	import { api } from '$lib/api/client';
	import type { components } from '$lib/types/schema';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import * as Card from '$lib/components/ui/card';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Loader from '@lucide/svelte/icons/loader';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	type AIResponse = components['schemas']['AIResponse'];

	let prompt = $state('');
	let isAnalyzing = $state(false);
	let isDeployed = $state(false);
	let errorMessage = $state('');

	async function interpretCommand() {
		if (!prompt) return;

		isAnalyzing = true;
		errorMessage = '';

		try {
			const result = await api.post<AIResponse>('/api/ai/interpret', { text: prompt });

			if (result.success && result.data) {
				sessionStorage.setItem('ai_blueprint', JSON.stringify(result.data));
				goto(resolve('/dashboard/edit/new?source=ai'));
			} else {
				errorMessage = result.error || 'AI could not structure that request.';
			}
		} catch (err) {
			errorMessage =
				(err as { message?: string })?.message || 'Server connection lost. Please try again.';
		} finally {
			isAnalyzing = false;
		}
	}
</script>

<div class="min-h-screen bg-background p-6 lg:p-12">
	<div class="mx-auto max-w-5xl space-y-6">
		<div class="flex flex-col gap-4">
			<div class="flex flex-row justify-between">
				<Button
					variant="ghost"
					size="sm"
					class="w-fit gap-2"
					onclick={() => goto(resolve('/dashboard'))}
				>
					<ChevronLeft class="h-4 w-4" /> Back to Fleet
				</Button>
				<Button
					variant="outline"
					class="w-fit gap-2"
					disabled={isAnalyzing || isDeployed}
					onclick={() => goto(resolve('/dashboard/edit/new'))}
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
