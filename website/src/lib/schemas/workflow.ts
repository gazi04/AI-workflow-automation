export const TRIGGER_DEFINITIONS = {
	schedule: {
		label: 'Schedule',
		fields: [
			{ key: 'cron', label: 'Cron Expression', type: 'text' },
			{ key: 'description', label: 'Description', type: 'text' }
		]
	},
	email_received: {
		label: 'Email Received',
		fields: [
			{ key: 'from', label: 'From Email', type: 'text' },
			{ key: 'subject_contains', label: 'Subject Contains', type: 'text' }
		]
	},
	new_sheet_row: {
		label: 'New Sheet Row',
		fields: [{ key: 'spreadsheet_id', label: 'Spreadsheet ID', type: 'text' }]
	}
} as const;

export const ACTION_DEFINITIONS = {
	smart_draft: {
		label: 'Smart Draft (AI)',
		fields: [{ key: 'user_prompt', label: 'Instructions for AI', type: 'textarea' }]
	},
	send_email: {
		label: 'Send Email',
		fields: [
			{ key: 'to', label: 'To', type: 'text' },
			{ key: 'subject', label: 'Subject', type: 'text' },
			{ key: 'body', label: 'Body', type: 'textarea' }
		]
	},
	reply_email: {
		label: 'Reply Email',
		fields: [{ key: 'body', label: 'Body', type: 'textarea' }]
	},
	send_slack_message: {
		label: 'Slack Message',
		fields: [
			{ key: 'channel', label: 'Channel', type: 'text' },
			{ key: 'message', label: 'Message', type: 'textarea' }
		]
	},
	create_document: {
		label: 'Google Doc',
		fields: [
			{ key: 'title', label: 'Title', type: 'text' },
			{ key: 'content', label: 'Content', type: 'textarea' }
		]
	},
	label_email: {
		label: 'Label Email',
		fields: []
	}
} as const;
