export const ACTION_DEFINITIONS = {
	smart_draft: {
		label: 'Smart Draft (AI)',
		fields: [
			{ key: 'user_prompt', label: 'Instructions for AI', type: 'textarea' },
			{ key: 'model', label: 'AI Model', type: 'select', options: ['gpt-4', 'claude-3'] }
		]
	},
	email_received: {
		label: 'Email Received',
		fields: [
			{ key: 'from', label: 'Sender Email', type: 'text' },
			{ key: 'subject_contains', label: 'Subject Filter', type: 'text' }
		]
	},
	send_email: {
		label: 'Send Email',
		fields: [
			{ key: 'to', label: 'Recipient', type: 'text' },
			{ key: 'subject', label: 'Subject Line', type: 'text' },
			{ key: 'body', label: 'Email Body', type: 'textarea' }
		]
	}
};
