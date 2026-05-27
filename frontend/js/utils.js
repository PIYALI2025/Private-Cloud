const BASE_URL = window.location.origin;

const Utils = {
    showToast(message, type = 'info') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        container.appendChild(toast);

        // Trigger animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        // Remove after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3000);
    },

    async apiFetch(endpoint, options = {}) {
        const token = localStorage.getItem('token');
        const headers = {
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // Only set Content-Type to JSON if not already set and not FormData
        if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const config = {
            ...options,
            headers,
        };

        try {
            const response = await fetch(`${BASE_URL}${endpoint}`, config);
            
            // Handle 401 Unauthorized globally
            if (response.status === 401 && !endpoint.includes('/auth/login')) {
                localStorage.removeItem('token');
                window.location.href = 'login.html';
                return null;
            }

            if (!response.ok) {
                let errorMsg = 'An error occurred';
                try {
                    const errorData = await response.json();
                    if (Array.isArray(errorData.detail)) {
                        errorMsg = errorData.detail.map(e => `${e.loc ? e.loc[e.loc.length-1] + ': ' : ''}${e.msg}`).join(', ');
                    } else {
                        errorMsg = errorData.detail || errorMsg;
                    }
                } catch (e) {
                    errorMsg = `HTTP Error ${response.status}`;
                }
                throw new Error(errorMsg);
            }

            // For file downloads
            if (options.isDownload) {
                return response.blob();
            }

            return await response.json();
        } catch (error) {
            console.error('API Fetch Error:', error);
            throw error;
        }
    },

    logout() {
        localStorage.removeItem('token');
        window.location.href = 'login.html';
    }
};
