const Auth = {
    currentMode: 'login', // 'login' or 'signup'

    init() {
        // Redirect if already logged in
        if (localStorage.getItem('token')) {
            window.location.href = 'index.html';
        }
    },

    switchTab(mode) {
        this.currentMode = mode;
        
        const tabLogin = document.getElementById('tab-login');
        const tabSignup = document.getElementById('tab-signup');
        const submitText = document.getElementById('submit-text');

        if (mode === 'login') {
            tabLogin.className = "flex-1 py-2 text-sm font-medium rounded-md bg-slate-700 text-white shadow transition-all";
            tabSignup.className = "flex-1 py-2 text-sm font-medium rounded-md text-slate-400 hover:text-white transition-all";
            submitText.textContent = "Login to Vault";
        } else {
            tabSignup.className = "flex-1 py-2 text-sm font-medium rounded-md bg-slate-700 text-white shadow transition-all";
            tabLogin.className = "flex-1 py-2 text-sm font-medium rounded-md text-slate-400 hover:text-white transition-all";
            submitText.textContent = "Create Account";
        }
    },

    setLoading(isLoading) {
        const btn = document.getElementById('submit-btn');
        const text = document.getElementById('submit-text');
        const spinner = document.getElementById('submit-spinner');

        if (isLoading) {
            btn.disabled = true;
            btn.classList.add('opacity-75', 'cursor-not-allowed');
            text.classList.add('hidden');
            spinner.classList.remove('hidden');
        } else {
            btn.disabled = false;
            btn.classList.remove('opacity-75', 'cursor-not-allowed');
            text.classList.remove('hidden');
            spinner.classList.add('hidden');
        }
    },

    async handleSubmit(e) {
        e.preventDefault();
        
        const usernameInput = document.getElementById('username').value;
        const passwordInput = document.getElementById('password').value;

        if (!usernameInput || !passwordInput) {
            Utils.showToast('Please fill in all fields', 'error');
            return;
        }

        this.setLoading(true);

        try {
            if (this.currentMode === 'signup') {
                await Utils.apiFetch('/auth/signup', {
                    method: 'POST',
                    body: JSON.stringify({
                        username: usernameInput,
                        password: passwordInput
                    })
                });
                Utils.showToast('Account created! Logging in...', 'success');
            }

            // Perform Login (either explicit login or auto-login after signup)
            // OAuth2 requires form data (URL encoded), not JSON!
            const formData = new URLSearchParams();
            formData.append('username', usernameInput);
            formData.append('password', passwordInput);

            const data = await Utils.apiFetch('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: formData.toString()
            });

            if (data && data.access_token) {
                localStorage.setItem('token', data.access_token);
                window.location.href = 'index.html';
            }

        } catch (error) {
            Utils.showToast(error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => Auth.init());
