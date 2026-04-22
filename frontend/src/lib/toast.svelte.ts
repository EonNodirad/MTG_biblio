type ToastState = { message: string; type: 'loading' | 'success' | 'error' } | null;

let _toast = $state<ToastState>(null);
let _timer: ReturnType<typeof setTimeout> | null = null;

export const toast = {
	get current() { return _toast; },

	loading(message: string) {
		if (_timer) { clearTimeout(_timer); _timer = null; }
		_toast = { message, type: 'loading' };
	},

	success(message: string, duration = 3000) {
		if (_timer) clearTimeout(_timer);
		_toast = { message, type: 'success' };
		_timer = setTimeout(() => { _toast = null; _timer = null; }, duration);
	},

	error(message: string, duration = 4000) {
		if (_timer) clearTimeout(_timer);
		_toast = { message, type: 'error' };
		_timer = setTimeout(() => { _toast = null; _timer = null; }, duration);
	},

	clear() {
		if (_timer) { clearTimeout(_timer); _timer = null; }
		_toast = null;
	},
};
