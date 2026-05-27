const Dashboard = {
    files: [],
    currentTab: 'my-vault',
    discoverySearchTimeout: null,
    
    init() {
        if (!localStorage.getItem('token')) {
            window.location.href = 'login.html';
            return;
        }

        this.setupDragAndDrop();
        this.setupSearch();
        this.setupDiscoverySearch();
        this.loadFiles();
        this.loadUserProfile();
        this.checkPendingRequests();
        
        // Poll for notifications
        setInterval(() => this.checkPendingRequests(), 10000);
    },

    setupDragAndDrop() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-active'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-active'), false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            this.handleFiles(files);
        });

        fileInput.addEventListener('change', function() {
            Dashboard.handleFiles(this.files);
        });
    },

    setupSearch() {
        const searchInput = document.getElementById('search-input');
        let timeout = null;
        
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                const query = e.target.value.trim();
                this.loadFiles(query);
            }, 500);
        });
    },

    setupDiscoverySearch() {
        const userInput = document.getElementById('user-search-input');
        userInput.addEventListener('input', (e) => {
            clearTimeout(this.discoverySearchTimeout);
            this.discoverySearchTimeout = setTimeout(() => {
                const query = e.target.value.trim();
                if (query.length > 0) {
                    this.searchUsers(query);
                } else {
                    document.getElementById('user-search-results').innerHTML = '<div class="text-center py-6 text-slate-500 text-sm">Type a name to search...</div>';
                }
            }, 300);
        });
    },

    async handleFiles(files) {
        if (!files || files.length === 0) return;

        const overlay = document.getElementById('upload-overlay');
        overlay.classList.remove('hidden');

        try {
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const formData = new FormData();
                formData.append('file', file);

                await Utils.apiFetch('/upload', {
                    method: 'POST',
                    body: formData
                });
            }

            Utils.showToast(`${files.length} file(s) uploaded successfully!`, 'success');
            this.loadFiles(); // Refresh grid
        } catch (error) {
            Utils.showToast(`Upload failed: ${error.message}`, 'error');
        } finally {
            overlay.classList.add('hidden');
            document.getElementById('file-input').value = ''; // Reset
        }
    },

    async loadFiles(searchQuery = '') {
        try {
            let endpoint = this.currentTab === 'shared' ? '/files/shared' : '/files/search';
            
            // Search is only supported in personal vault (GET /files/search)
            if (this.currentTab === 'my-vault' && searchQuery) {
                endpoint += `?name=${encodeURIComponent(searchQuery)}`;
            }

            const data = await Utils.apiFetch(endpoint);
            this.files = data;
            this.renderFileGrid();
        } catch (error) {
            Utils.showToast('Failed to load files.', 'error');
        }
    },

    switchTab(tab) {
        if (this.currentTab === tab) return;
        this.currentTab = tab;

        const myVaultBtn = document.getElementById('tab-my-vault');
        const sharedWorkspaceBtn = document.getElementById('tab-shared-workspace');

        if (tab === 'my-vault') {
            myVaultBtn.className = "text-2xl font-bold text-white tracking-tight border-b-2 border-brand-500 pb-1 focus:outline-none transition-all";
            sharedWorkspaceBtn.className = "text-2xl font-bold text-slate-400 hover:text-white tracking-tight pb-1 border-b-2 border-transparent focus:outline-none transition-all";
            document.getElementById('drop-zone').parentElement.classList.remove('hidden'); // Show upload zone
        } else {
            sharedWorkspaceBtn.className = "text-2xl font-bold text-white tracking-tight border-b-2 border-brand-500 pb-1 focus:outline-none transition-all";
            myVaultBtn.className = "text-2xl font-bold text-slate-400 hover:text-white tracking-tight pb-1 border-b-2 border-transparent focus:outline-none transition-all";
            document.getElementById('drop-zone').parentElement.classList.add('hidden'); // Hide upload zone for shared workspace
        }

        this.loadFiles();
    },

    renderFileGrid() {
        const grid = document.getElementById('file-grid');
        grid.innerHTML = '';

        if (this.files.length === 0) {
            if (this.currentTab === 'my-vault') {
                grid.innerHTML = `
                    <div class="col-span-full py-12 text-center text-slate-500">
                        <svg class="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
                        <p class="text-lg font-medium">Vault is empty</p>
                        <p class="text-sm">Upload a file to securely store it</p>
                    </div>
                `;
            } else {
                grid.innerHTML = `
                    <div class="col-span-full py-12 text-center text-slate-500">
                        <svg class="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                        <p class="text-lg font-medium">Workspace is empty</p>
                        <p class="text-sm">No files have been shared with you yet</p>
                    </div>
                `;
            }
            return;
        }

        this.files.forEach(file => {
            const date = new Date(file.upload_date).toLocaleDateString();
            const iconSvg = this.getFileIcon(file.file_type);
            const isMyVault = this.currentTab === 'my-vault';

            // Create card element
            const card = document.createElement('div');
            card.className = "bg-slate-800 border border-slate-700 rounded-xl overflow-hidden hover:border-slate-500 transition-colors group flex flex-col";
            
            card.innerHTML = `
                <div class="h-32 bg-slate-900/50 flex items-center justify-center relative p-4 group-hover:bg-slate-900/80 transition-colors">
                    ${iconSvg}
                    
                    ${isMyVault ? `
                    <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                        <button onclick="Dashboard.openEditModal(${file.id}, '${file.filename.replace(/'/g, "\\'")}')" class="p-1.5 bg-slate-700 rounded hover:bg-brand-500 text-white transition-colors" title="Rename">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
                        </button>
                    </div>
                    ` : ''}
                </div>
                
                <div class="p-4 flex-1 flex flex-col">
                    <h4 class="text-sm font-medium text-white truncate mb-1" title="${file.filename}">${file.filename}</h4>
                    <p class="text-xs text-slate-400 mb-4">${date} • ${file.file_type.split('/')[1] || file.file_type}</p>
                    
                    <div class="mt-auto flex gap-2">
                        ${isMyVault ? `
                        <button onclick="Dashboard.requestShareLink(${file.id})" class="flex-1 flex items-center justify-center gap-1 py-1 px-1.5 bg-slate-700 hover:bg-slate-600 rounded text-[11px] font-medium text-white transition-colors" title="Share Link">
                            Share
                        </button>
                        ` : ''}
                        <button onclick="Dashboard.triggerPreview(${file.id})" class="flex-1 flex items-center justify-center gap-1 py-1 px-1.5 bg-slate-700 hover:bg-slate-600 rounded text-[11px] font-medium text-white transition-colors" title="Open inline">
                            Open
                        </button>
                        <button onclick="Dashboard.triggerDownload(${file.id})" class="flex-1 flex items-center justify-center gap-1 py-1 px-1.5 bg-brand-600 hover:bg-brand-500 rounded text-[11px] font-medium text-white transition-colors" title="Download">
                            Download
                        </button>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
    },

    getFileIcon(mime) {
        if (mime.includes('image')) {
            return `<svg class="w-12 h-12 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>`;
        }
        if (mime.includes('pdf')) {
            return `<svg class="w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>`;
        }
        if (mime.includes('text')) {
            return `<svg class="w-12 h-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>`;
        }
        return `<svg class="w-12 h-12 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path></svg>`;
    },

    async requestShareLink(fileId) {
        try {
            const data = await Utils.apiFetch(`/files/${fileId}/regenerate-slug`, {
                method: 'PATCH'
            });
            const slug = data.new_slug;
            const link = `${BASE_URL}/download/${slug}`;
            
            await navigator.clipboard.writeText(link);
            Utils.showToast('Secure link generated and copied to clipboard!', 'success');
        } catch (error) {
            Utils.showToast('Failed to generate link', 'error');
        }
    },

    async triggerDownload(fileId) {
        try {
            const file = this.files.find(f => f.id === fileId);
            if (!file) throw new Error("File not found");
            
            let slug = file.share_slug;
            
            if (this.currentTab === 'my-vault') {
                const data = await Utils.apiFetch(`/files/${fileId}/regenerate-slug`, {
                    method: 'PATCH'
                });
                slug = data.new_slug;
            }
            
            if (!slug) {
                throw new Error("Unable to resolve download slug");
            }
            
            Utils.showToast('Decrypting file...', 'info');
            
            const blob = await Utils.apiFetch(`/download/${slug}`, { isDownload: true });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = file.filename;
            
            document.body.appendChild(a);
            a.click();
            
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            Utils.showToast('Download complete!', 'success');
        } catch (error) {
            Utils.showToast(`Download failed: ${error.message}`, 'error');
        }
    },

    async checkPendingRequests() {
        try {
            const data = await Utils.apiFetch('/notifications');
            const badge = document.getElementById('requests-badge');
            
            if (data && data.length > 0) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        } catch (error) {
            console.error("Failed to fetch requests", error);
        }
    },

    async openRequestsModal() {
        const modal = document.getElementById('requests-modal');
        const content = document.getElementById('requests-modal-content');
        
        modal.classList.remove('hidden');
        setTimeout(() => content.classList.remove('scale-95'), 10);
        
        await this.loadPendingRequests();
    },

    closeRequestsModal() {
        const modal = document.getElementById('requests-modal');
        const content = document.getElementById('requests-modal-content');
        
        content.classList.add('scale-95');
        setTimeout(() => modal.classList.add('hidden'), 150);
    },

    async loadPendingRequests() {
        const list = document.getElementById('requests-list');
        list.innerHTML = '<div class="text-center py-8 text-slate-500">Loading requests...</div>';

        try {
            const requests = await Utils.apiFetch('/notifications');
            
            if (requests.length === 0) {
                list.innerHTML = `
                    <div class="text-center py-10">
                        <svg class="w-12 h-12 text-slate-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
                        <p class="text-slate-400 font-medium">Inbox zero!</p>
                        <p class="text-slate-500 text-sm">No pending access requests.</p>
                    </div>`;
                return;
            }

            list.innerHTML = '';
            requests.forEach(req => {
                const div = document.createElement('div');
                div.className = "flex flex-col md:flex-row md:items-center md:justify-between p-4 bg-slate-900 rounded-lg border border-slate-700 gap-4";
                
                if (req.notification_type === "request_incoming") {
                    div.innerHTML = `
                        <div class="flex-1">
                            <div class="flex items-center justify-between">
                                <p class="text-white font-medium"><span class="text-brand-400">@${req.requester_username}</span> requested access</p>
                            </div>
                            <p class="text-slate-400 text-sm mt-1">File: <span class="text-white font-semibold">${req.file_name}</span></p>
                            ${req.message ? `<p class="text-slate-500 text-xs italic mt-1 bg-slate-950/40 p-2 rounded border border-slate-800">${req.message}</p>` : ''}
                        </div>
                        <div class="flex gap-2 justify-end">
                            <button onclick="Dashboard.handleRequest(${req.request_id}, 'deny')" class="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-red-500/20 hover:text-red-400 text-slate-300 text-sm font-medium transition-colors">Deny</button>
                            <button onclick="Dashboard.handleRequest(${req.request_id}, 'approve')" class="px-3 py-1.5 rounded-md bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors">Approve</button>
                        </div>
                    `;
                } else {
                    const isApproved = req.notification_type === "request_approved";
                    const alertColor = isApproved ? "text-emerald-400" : "text-rose-400";
                    div.innerHTML = `
                        <div class="flex-1">
                            <div class="flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full ${isApproved ? 'bg-emerald-500' : 'bg-rose-500'}"></span>
                                <p class="text-white font-medium ${alertColor}">${isApproved ? 'Access Approved!' : 'Access Denied'}</p>
                            </div>
                            <p class="text-slate-400 text-sm mt-1">${req.message}</p>
                        </div>
                        <div class="flex gap-2 justify-end">
                            <button onclick="Dashboard.dismissNotification(${req.id})" class="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors">Dismiss</button>
                        </div>
                    `;
                }
                list.appendChild(div);
            });

        } catch (error) {
            list.innerHTML = '<div class="text-center py-8 text-red-400">Failed to load requests</div>';
        }
    },

    async handleRequest(requestId, action) {
        try {
            await Utils.apiFetch(`/access/respond/${requestId}`, {
                method: 'PATCH',
                body: JSON.stringify({ response: action === 'approve' ? 'approved' : 'rejected' })
            });
            Utils.showToast(`Request ${action}d successfully`, 'success');
            await this.loadPendingRequests();
            await this.checkPendingRequests();
        } catch (error) {
            Utils.showToast(`Failed to ${action} request`, 'error');
        }
    },

    async dismissNotification(notifId) {
        try {
            await Utils.apiFetch(`/notifications/${notifId}/read`, {
                method: 'PATCH'
            });
            Utils.showToast("Notification cleared", "success");
            await this.loadPendingRequests();
            await this.checkPendingRequests();
        } catch (error) {
            Utils.showToast("Failed to clear notification", "error");
        }
    },

    openDiscoveryModal() {
        document.getElementById('discovery-modal').classList.remove('hidden');
        document.getElementById('user-search-input').value = '';
        document.getElementById('user-search-results').innerHTML = '<div class="text-center py-6 text-slate-500 text-sm">Type a name to search...</div>';
    },

    closeDiscoveryModal() {
        document.getElementById('discovery-modal').classList.add('hidden');
    },

    async searchUsers(query) {
        const resultsDiv = document.getElementById('user-search-results');
        resultsDiv.innerHTML = '<div class="text-center py-6 text-slate-500 text-sm">Searching...</div>';
        
        try {
            const users = await Utils.apiFetch(`/users/search?q=${encodeURIComponent(query)}`);
            if (users.length === 0) {
                resultsDiv.innerHTML = '<div class="text-center py-6 text-slate-500 text-sm">No users found</div>';
                return;
            }

            resultsDiv.innerHTML = '';
            users.forEach(user => {
                const div = document.createElement('div');
                div.className = "flex flex-col p-4 bg-slate-900 rounded-lg border border-slate-700 gap-3";
                div.innerHTML = `
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span class="text-white font-medium">@${user.username}</span>
                    </div>
                    <div class="flex flex-col gap-2">
                        <input type="text" id="filename-for-${user.id}" placeholder="File Name (extension optional)..." class="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 transition-all">
                        <input type="text" id="message-for-${user.id}" placeholder="Type a request message..." class="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 transition-all">
                        <div class="flex flex-col gap-1">
                            <span class="text-[10px] text-slate-400 font-semibold px-1">Access Duration</span>
                            <select id="duration-for-${user.id}" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-brand-500 transition-all">
                                <option value="forever">Forever (Permanent)</option>
                                <option value="1day">1 Day</option>
                                <option value="7days">7 Days</option>
                                <option value="1month">1 Month</option>
                                <option value="1year">1 Year</option>
                            </select>
                        </div>
                        <button onclick="Dashboard.requestAccessForUser(${user.id})" class="bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold py-1.5 rounded transition-colors w-full mt-1">Request Access</button>
                    </div>
                `;
                resultsDiv.appendChild(div);
            });
        } catch (error) {
            resultsDiv.innerHTML = '<div class="text-center py-6 text-red-400 text-sm">Error searching users</div>';
        }
    },

    async requestAccessForUser(userId) {
        const fileInput = document.getElementById(`filename-for-${userId}`);
        const msgInput = document.getElementById(`message-for-${userId}`);
        const durationInput = document.getElementById(`duration-for-${userId}`);
        
        const filename = fileInput.value.trim();
        const message = msgInput.value.trim();
        const duration = durationInput ? durationInput.value : "forever";
        
        if (!filename) {
            Utils.showToast("Please enter the requested file name", "warning");
            return;
        }

        try {
            const response = await Utils.apiFetch('/access/request', {
                method: 'POST',
                body: JSON.stringify({
                    owner_id: userId,
                    filename: filename,
                    message: message || "No message provided.",
                    duration: duration
                })
            });
            
            if (response && response.status === "multiple_choices") {
                this.currentChoiceState = {
                    userId: userId,
                    filename: filename,
                    message: message || "No message provided.",
                    duration: duration,
                    choices: response.choices
                };
                this.openChoicesModal(response.choices);
                return;
            }

            Utils.showToast("Access request submitted successfully!", "success");
            this.closeDiscoveryModal();
        } catch (error) {
            Utils.showToast(`Request failed: ${error.message}`, "error");
        }
    },

    openChoicesModal(choices) {
        const container = document.getElementById('choices-container');
        container.innerHTML = '';
        
        choices.forEach((choice, idx) => {
            const div = document.createElement('label');
            div.className = "flex items-center gap-3 p-3 bg-slate-900 rounded-lg border border-slate-700 cursor-pointer hover:border-slate-500 transition-colors mb-2";
            div.innerHTML = `
                <input type="radio" name="selected-choice" value="${choice.id}" ${idx === 0 ? 'checked' : ''} class="w-4 h-4 text-brand-600 bg-slate-800 border-slate-700 focus:ring-brand-500">
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-white truncate">${choice.filename}</p>
                    <p class="text-xs text-slate-400">${choice.file_type}</p>
                </div>
            `;
            container.appendChild(div);
        });
        
        document.getElementById('choices-modal').classList.remove('hidden');
    },

    closeChoicesModal() {
        document.getElementById('choices-modal').classList.add('hidden');
        this.currentChoiceState = null;
    },

    async submitSelectedChoice() {
        if (!this.currentChoiceState) return;
        
        const selectedRadio = document.querySelector('input[name="selected-choice"]:checked');
        if (!selectedRadio) {
            Utils.showToast("Please select a file.", "warning");
            return;
        }
        
        const fileId = parseInt(selectedRadio.value);
        const { userId, filename, message, duration } = this.currentChoiceState;
        
        try {
            await Utils.apiFetch('/access/request', {
                method: 'POST',
                body: JSON.stringify({
                    owner_id: userId,
                    filename: filename,
                    message: message,
                    duration: duration,
                    file_id: fileId
                })
            });
            
            Utils.showToast("Access request submitted successfully!", "success");
            this.closeChoicesModal();
            this.closeDiscoveryModal();
        } catch (error) {
            Utils.showToast(`Request failed: ${error.message}`, "error");
        }
    },

    openEditModal(id, filename) {
        document.getElementById('edit-file-id').value = id;
        document.getElementById('edit-filename-input').value = filename;
        document.getElementById('edit-modal').classList.remove('hidden');
    },

    closeEditModal() {
        document.getElementById('edit-modal').classList.add('hidden');
    },

    async saveRename() {
        const id = document.getElementById('edit-file-id').value;
        const newName = document.getElementById('edit-filename-input').value.trim();
        
        if (!newName) return;

        try {
            await Utils.apiFetch(`/files/${id}/rename`, {
                method: 'PATCH',
                body: JSON.stringify({ new_name: newName })
            });
            
            Utils.showToast('File renamed successfully', 'success');
            this.closeEditModal();
            this.loadFiles();
        } catch (error) {
            Utils.showToast('Failed to rename file', 'error');
        }
    },

    async loadUserProfile() {
        try {
            const user = await Utils.apiFetch('/user/me');
            if (user) {
                document.getElementById('nav-username').textContent = `@${user.username}`;
                if (user.profile_photo) {
                    const photoUrl = `${BASE_URL}/user/profile-photo/${user.username}`;
                    document.getElementById('nav-profile-img').src = photoUrl;
                    document.getElementById('modal-profile-img').src = photoUrl;
                }
            }
        } catch (error) {
            console.error("Failed to load user profile", error);
        }
    },

    openProfileModal() {
        document.getElementById('profile-modal').classList.remove('hidden');
    },

    closeProfileModal() {
        document.getElementById('profile-modal').classList.add('hidden');
    },

    async handleProfilePhotoUpload(files) {
        if (!files || files.length === 0) return;
        const file = files[0];
        if (!file.type.startsWith('image/')) {
            Utils.showToast("Only image files are allowed", "warning");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${BASE_URL}/user/profile-photo`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Upload failed");
            }

            const data = await response.json();
            Utils.showToast("Profile photo updated successfully!", "success");
            
            this.loadUserProfile();
            this.closeProfileModal();
        } catch (error) {
            Utils.showToast(`Upload failed: ${error.message}`, "error");
        }
    },

    async triggerPreview(fileId) {
        const file = this.files.find(f => f.id === fileId);
        if (!file) {
            Utils.showToast("File not found", "error");
            return;
        }

        let slug = file.share_slug;
        if (this.currentTab === 'my-vault') {
            try {
                const data = await Utils.apiFetch(`/files/${fileId}/regenerate-slug`, {
                    method: 'PATCH'
                });
                slug = data.new_slug;
            } catch (error) {
                console.error("Failed to regenerate slug during preview", error);
            }
        }

        const token = localStorage.getItem('token');
        const url = `${BASE_URL}/preview/${slug}?token=${token}`;
        window.open(url, '_blank');
    }
};

document.addEventListener('DOMContentLoaded', () => Dashboard.init());
