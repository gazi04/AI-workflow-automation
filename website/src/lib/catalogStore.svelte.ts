import type { components } from '$lib/types/schema';
import { api } from '$lib/api/client';

type WorkflowCatalog = components['schemas']['WorkflowCatalog'];
type NodeDefinition = components['schemas']['NodeDefinition'];

class CatalogStore {
    catalog = $state<WorkflowCatalog | null>(null);
    isLoading = $state(false);
    error = $state<string | null>(null);

    async load() {
        if (this.catalog) return;
        this.isLoading = true;
        try {
            this.catalog = await api.get<WorkflowCatalog>('/api/workflow/catalog');
        } catch (e: any) {
            this.error = e.message ?? 'Failed to load catalog';
        } finally {
            this.isLoading = false;
        }
    }

    // Look up a single node definition by type across triggers and actions
    getNodeDef(type: string): NodeDefinition | undefined {
        const all = [...(this.catalog?.triggers ?? []), ...(this.catalog?.actions ?? [])];
        return all.find((n) => n.type === type);
    }
}

export const catalogStore = new CatalogStore();
