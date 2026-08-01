import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],

	optimizeDeps: {
		// Plain-JS dependencies that are only reached from a lazily-loaded route.
		// Left to itself Vite discovers them mid-request, re-runs the optimizer and
		// forces a full page reload — that reload is most of the first-load wait.
		// Svelte component libraries (@xyflow/svelte, bits-ui, svelte-sonner,
		// @lucide/svelte) are deliberately absent: vite-plugin-svelte handles those
		// and listing them here breaks their compilation.
		include: [
			'dagre',
			'cronstrue',
			'clsx',
			'tailwind-merge',
			'tailwind-variants',
			'@internationalized/date'
		]
	},

	server: {
		host: '0.0.0.0',

		// Compile the routes and the editor canvas in the background at boot instead
		// of on the first request that needs them. ssrFiles matters as much as
		// clientFiles here: SvelteKit renders every page on the server first, so
		// without it the editor route still paid ~7s to compile @xyflow/svelte and
		// its component tree on the first hit.
		warmup: {
			clientFiles: [
				'./src/routes/**/+page.svelte',
				'./src/routes/**/+layout.svelte',
				'./src/lib/components/editor/*.svelte'
			],
			ssrFiles: [
				'./src/routes/**/+page.svelte',
				'./src/routes/**/+layout.svelte',
				'./src/lib/components/editor/*.svelte'
			]
		},

		watch: {
			// Under a bind mount chokidar otherwise walks these and holds a watcher
			// per file, which costs both memory and startup time.
			ignored: ['**/node_modules/**', '**/.svelte-kit/**', '**/.git/**']
		}
	}
});
