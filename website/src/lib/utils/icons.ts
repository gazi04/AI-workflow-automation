import type { Component } from 'svelte';
import type { IconProps } from '@lucide/svelte';
import Mail from '@lucide/svelte/icons/mail';
import Hand from '@lucide/svelte/icons/hand';
import Calendar from '@lucide/svelte/icons/calendar';
import FileSpreadsheet from '@lucide/svelte/icons/file-spreadsheet';
import Send from '@lucide/svelte/icons/send';
import Reply from '@lucide/svelte/icons/reply';
import Tag from '@lucide/svelte/icons/tag';
import Sparkles from '@lucide/svelte/icons/sparkles';
import FileText from '@lucide/svelte/icons/file-text';
import Slack from '@lucide/svelte/icons/slack';
import Circle from '@lucide/svelte/icons/circle';
import Split from '@lucide/svelte/icons/split';
import GitBranch from '@lucide/svelte/icons/git-branch';

export const ICON_MAP: Record<string, Component<IconProps>> = {
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
