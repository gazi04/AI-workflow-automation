/** The handle a node's failure routes through — mirrors backend `SourceHandle`. */
export const ERROR_HANDLE = 'error_path';

const ERROR_EDGE_STYLE = 'stroke: #ef4444; stroke-width: 2;';

/** Structural shape shared by an xyflow `Edge` and a freshly drawn `Connection`. */
type EdgeLike = {
	sourceHandle?: string | null;
	style?: string;
	label?: string;
};

/**
 * Paint error-path edges red so a failure route is distinguishable from the
 * normal success flow at a glance. Non-error edges are returned untouched.
 */
export function decorateEdge<T extends EdgeLike>(edge: T): T {
	if (edge.sourceHandle !== ERROR_HANDLE) return edge;

	return {
		...edge,
		label: edge.label ?? 'on error',
		style: edge.style ? `${edge.style} ${ERROR_EDGE_STYLE}` : ERROR_EDGE_STYLE,
		labelStyle: 'fill: #ef4444; font-size: 10px; font-weight: 700;'
	};
}

/** The named handles the backend accepts on an edge. */
export type SourceHandle = 'true_path' | 'false_path' | typeof ERROR_HANDLE;

const SOURCE_HANDLES: SourceHandle[] = ['true_path', 'false_path', ERROR_HANDLE];

/**
 * Narrow a canvas edge's free-form `sourceHandle` to what the backend schema
 * accepts. Anything unrecognised (including xyflow's default `null`) is the
 * implicit success path.
 */
export function toSourceHandle(value: string | null | undefined): SourceHandle | null {
	return SOURCE_HANDLES.includes(value as SourceHandle) ? (value as SourceHandle) : null;
}
