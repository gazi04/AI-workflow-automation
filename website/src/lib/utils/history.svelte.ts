export class HistoryManager<T> {
    private undoStack = $state<string[]>([]);
    private redoStack = $state<string[]>([]);
    private maxDepth = 50;

    push(state: T) {
        const serialized = JSON.stringify(state);
        
        if (this.undoStack.length > 0 && this.undoStack[this.undoStack.length - 1] === serialized) {
            return;
        }

        this.undoStack.push(serialized);
        this.redoStack = [];

        if (this.undoStack.length > this.maxDepth) {
            this.undoStack.shift();
        }
    }

    undo(currentState: T): T | null {
        if (this.undoStack.length <= 1) return null;

        const current = this.undoStack.pop()!;
        this.redoStack.push(current);

        return JSON.parse(this.undoStack[this.undoStack.length - 1]);
    }

    redo(): T | null {
        if (this.redoStack.length === 0) return null;

        const next = this.redoStack.pop()!;
        this.undoStack.push(next);

        return JSON.parse(next);
    }

    get canUndo() { return this.undoStack.length > 1; }
    get canRedo() { return this.redoStack.length > 0; }
}
