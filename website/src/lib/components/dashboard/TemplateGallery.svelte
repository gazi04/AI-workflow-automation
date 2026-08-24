<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api } from '$lib/api/client';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { ICON_MAP, DEFAULT_ICON } from '$lib/utils/icons';
	import Loader from '@lucide/svelte/icons/loader';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import { toast } from 'svelte-sonner';

	// Hand-written: schema.d.ts is regenerated out-of-band and does not yet
	// carry /api/workflow/templates.
	type TemplateSummary = {
		id: string;
		name: string;
		description: string;
		category: string;
		icon: string;
		steps: string[];
	};

	let templates = $state<TemplateSummary[]>([]);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let creatingId = $state<string | null>(null);

	onMount(fetchTemplates);

	async function fetchTemplates() {
		isLoading = true;
		error = null;
		try {
			templates = await api.get<TemplateSummary[]>('/api/workflow/templates');
		} catch (err) {
			error = (err as { detail?: string }).detail || 'Could not load templates.';
		} finally {
			isLoading = false;
		}
	}

	async function useTemplate(template: TemplateSummary) {
		if (creatingId) return;
		creatingId = template.id;
		try {
			const created = await api.post<{ id: string }>(
				`/api/workflow/templates/${template.id}/instantiate`,
				{}
			);
			toast.success(`"${template.name}" created. It starts paused — review it, then activate.`);
			await goto(resolve(`/dashboard/edit/${created.id}`));
		} catch (err) {
			toast.error((err as { detail?: string }).detail || 'Could not create the workflow.');
			creatingId = null;
		}
	}
</script>

{#if isLoading}
	<div class="flex h-32 items-center justify-center">
		<Loader class="h-6 w-6 animate-spin text-muted-foreground" />
	</div>
{:else if error}
	<div class="flex flex-col items-center gap-3 py-8 text-center">
		<p class="text-sm text-muted-foreground">{error}</p>
		<Button variant="outline" onclick={fetchTemplates}>Try Again</Button>
	</div>
{:else if templates.length > 0}
	<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
		{#each templates as template (template.id)}
			{@const Icon = ICON_MAP[template.icon] || DEFAULT_ICON}

			<Card.Root class="flex flex-col justify-between transition-all hover:border-primary/50">
				<Card.Header>
					<div class="flex items-start justify-between">
						<div class="flex h-12 w-12 items-center justify-center rounded-lg bg-muted">
							<Icon class="h-6 w-6 text-foreground" />
						</div>
						<Badge variant="secondary" class="uppercase">{template.category}</Badge>
					</div>

					<Card.Title class="mt-4 text-xl font-bold">{template.name}</Card.Title>
					<Card.Description class="line-clamp-3">{template.description}</Card.Description>
				</Card.Header>

				<Card.Content>
					<div class="flex flex-wrap gap-2">
						{#each template.steps as step (step)}
							<Badge variant="outline" class="font-normal">{step}</Badge>
						{/each}
					</div>
				</Card.Content>

				<Card.Footer class="border-t bg-muted/20 pt-4">
					<Button
						class="w-full"
						disabled={creatingId !== null}
						onclick={() => useTemplate(template)}
					>
						{#if creatingId === template.id}
							<Loader class="mr-2 h-4 w-4 animate-spin" /> Creating...
						{:else}
							Use this template <ArrowRight class="ml-2 h-4 w-4" />
						{/if}
					</Button>
				</Card.Footer>
			</Card.Root>
		{/each}
	</div>
{/if}
