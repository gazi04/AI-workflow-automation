import {
	Mail,
	Hand,
	Calendar,
	FileSpreadsheet,
	Send,
	Reply,
	Tag,
	Sparkles,
	FileText,
	Slack,
	Circle,
	Split,
    GitBranch
} from 'lucide-svelte';

export const ICON_MAP: Record<string, any> = {
	'lucide-mail': Mail,
	'lucide-hand': Hand,
	'lucide-calendar': Calendar,
	'lucide-file-spreadsheet': FileSpreadsheet,
	'lucide-send': Send,
	'lucide-reply': Reply,
	'lucide-tag': Tag,
	'lucide-sparkles': Sparkles,
	'lucide-file-text': FileText,
	'lucide-slack': Slack,
	'lucide-split': Split,
    'lucide-git-branch': GitBranch
};

export const DEFAULT_ICON = Circle;
