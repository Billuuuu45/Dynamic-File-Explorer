document.addEventListener('DOMContentLoaded', () => {
    const connectorsContainer = document.getElementById('connectors-container');

    // Fetch dynamic connector data from backend
    async function loadConnectors() {
        try {
            const response = await fetch('/api/connectors');
            if (!response.ok) throw new Error('Failed to fetch connectors');
            const connectors = await response.json();

            connectorsContainer.innerHTML = '';

            connectors.forEach(conn => {
                const card = document.createElement('div');
                card.className = 'connector-card';
                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-icon">${conn.icon}</div>
                        <div class="card-title-area">
                            <div class="card-title">${conn.title}</div>
                            <div class="card-subtitle">${conn.subtitle}</div>
                        </div>
                    </div>
                    <div class="card-desc">${conn.description}</div>
                    
                    <div class="card-stats">
                        <div class="stat-row">
                            <span class="stat-label">MCP server</span>
                            <span class="stat-val teal">${conn.mcp_server}</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Objects</span>
                            <span class="stat-val">${conn.objects}</span>
                        </div>
                    </div>
                    
                    <div class="card-footer">
                        <div class="footer-badges">
                            <div class="badge connected">
                                <span class="dot online"></span> ${conn.status}
                            </div>
                            <div class="badge">${conn.protocol}</div>
                        </div>
                        <div class="footer-time">${conn.time}</div>
                    </div>
                `;
                connectorsContainer.appendChild(card);
            });

        } catch (error) {
            connectorsContainer.innerHTML = `<div class="card-desc" style="color: red;">Error loading connectors: ${error.message}</div>`;
        }
    }

    // ----------------- NAVIGATION LOGIC -----------------
    const navDashboard = document.getElementById('nav-dashboard');
    const navFileExplorer = document.getElementById('nav-file-explorer');
    const viewDashboard = document.getElementById('view-dashboard');
    const viewFileExplorer = document.getElementById('view-file-explorer');

    navDashboard.addEventListener('click', (e) => {
        e.preventDefault();
        navFileExplorer.classList.remove('active');
        navDashboard.classList.add('active');
        viewFileExplorer.classList.add('hidden');
        viewDashboard.classList.remove('hidden');
    });

    navFileExplorer.addEventListener('click', (e) => {
        e.preventDefault();
        navDashboard.classList.remove('active');
        navFileExplorer.classList.add('active');
        viewDashboard.classList.add('hidden');
        viewFileExplorer.classList.remove('hidden');

        // Load folders if not loaded
        if (folderListEl.children.length <= 1) {
            loadFolders();
        }
    });

    // ----------------- FILE EXPLORER LOGIC -----------------
    const folderListEl = document.getElementById('folder-list');
    const fileListEl = document.getElementById('file-list');
    const detailsContentEl = document.getElementById('details-content');
    const currentPathEl = document.getElementById('current-path');

    let currentPath = '';

    const searchInput = document.getElementById('explorer-search');

    const highlightText = (text, q) => {
        if (!q) return text;
        const idx = text.toLowerCase().indexOf(q.toLowerCase());
        if (idx === -1) return text;
        const before = text.slice(0, idx);
        const match = text.slice(idx, idx + q.length);
        const after = text.slice(idx + q.length);
        return `${before}<span style="background-color: rgba(0, 210, 255, 0.3); color: #fff; border-radius: 2px;">${match}</span>${highlightText(after, q)}`;
    };

    async function loadFolders(searchQuery = '') {
        if (searchInput && !searchQuery && searchInput.value) searchInput.value = '';
        folderListEl.innerHTML = '<div class="loading">Loading folders...</div>';
        try {
            const url = searchQuery ? `/api/folders?search=${encodeURIComponent(searchQuery)}` : '/api/folders';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch folders');
            const folders = await response.json();

            folderListEl.innerHTML = '';

            if (!searchQuery) {
                const rootItem = createFolderElement('.. (Root)', '');
                folderListEl.appendChild(rootItem);
            }

            folders.forEach(folder => {
                const displayed = searchQuery ? highlightText(folder, searchQuery) : folder;
                const folderItem = createFolderElement(displayed, folder);
                folderListEl.appendChild(folderItem);
            });
        } catch (error) {
            folderListEl.innerHTML = `<div class="empty-state">Error: ${error.message}</div>`;
        }
    }

    function createFolderElement(displayName, path) {
        const div = document.createElement('div');
        div.className = 'folder-item';
        div.innerHTML = `<span class="folder-icon">📁</span><span>${displayName}</span>`;

        div.addEventListener('click', () => {
            document.querySelectorAll('.folder-item').forEach(el => el.classList.remove('active'));
            div.classList.add('active');

            currentPath = path;
            currentPathEl.textContent = '/' + currentPath;
            loadFiles(currentPath);
        });

        return div;
    }

    async function loadFiles(path, searchQuery = '') {
        if (searchInput && !searchQuery && searchInput.value) searchInput.value = '';
        fileListEl.innerHTML = '<tr><td colspan="3" class="loading">Loading files...</td></tr>';
        detailsContentEl.innerHTML = '<div class="empty-state">Select a file to view details</div>';

        try {
            let url = `/api/files?path=${encodeURIComponent(path || '')}`;
            if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch files');
            const files = await response.json();

            fileListEl.innerHTML = '';

            if (files.length === 0) {
                fileListEl.innerHTML = '<tr><td colspan="3" class="empty-state">This folder is empty</td></tr>';
                return;
            }

            files.forEach(file => {
                const tr = document.createElement('tr');
                tr.className = 'file-row';
                const displayedName = searchQuery ? highlightText(file.name, searchQuery) : file.name;
                tr.innerHTML = `
                    <td>📄 ${displayedName}</td>
                    <td>${file.type.toUpperCase()}</td>
                    <td>${formatBytes(file.size)}</td>
                `;

                tr.addEventListener('click', () => {
                    document.querySelectorAll('.file-row').forEach(el => el.classList.remove('active'));
                    tr.classList.add('active');

                    const fullPath = path ? `${path}/${file.name}` : file.name;
                    loadFileDetails(fullPath);
                });

                fileListEl.appendChild(tr);
            });
        } catch (error) {
            fileListEl.innerHTML = `<tr><td colspan="3" class="empty-state">Error: ${error.message}</td></tr>`;
        }
    }

    async function loadFileDetails(filePath) {
        detailsContentEl.innerHTML = '<div class="loading">Loading details...</div>';

        try {
            const encodedPath = encodeURIComponent(filePath);
            const [metaResponse, readResponse] = await Promise.all([
                fetch(`/api/metadata?path=${encodedPath}`),
                fetch(`/api/read?path=${encodedPath}`)
            ]);

            if (!metaResponse.ok) throw new Error('Failed to fetch metadata');
            if (!readResponse.ok) throw new Error('Failed to read file');

            const metadata = await metaResponse.json();
            const content = await readResponse.text();

            renderDetails(metadata, content);
        } catch (error) {
            detailsContentEl.innerHTML = `<div class="empty-state">Error: ${error.message}</div>`;
        }
    }

    function renderDetails(metadata, content) {
        const dateObj = new Date(metadata.modified_date);
        const formattedDate = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString();

        detailsContentEl.innerHTML = `
            <div class="metadata-section">
                <div class="metadata-item">
                    <span class="metadata-label">Name</span>
                    <span>${metadata.filename}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Type</span>
                    <span>${metadata.extension.toUpperCase()}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Size</span>
                    <span>${formatBytes(metadata.size)}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Modified</span>
                    <span>${formattedDate}</span>
                </div>
            </div>
            
            <div class="preview-section">
                <div class="preview-title">Content Preview</div>
                <div class="file-content-preview">${escapeHtml(content)}</div>
            </div>
        `;
    }

    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function escapeHtml(unsafe) {
        if (unsafe.startsWith('"') && unsafe.endsWith('"')) {
            try { unsafe = JSON.parse(unsafe); } catch (e) { }
        }
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ----------------- SEARCH LOGIC -----------------
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();

            debounceTimer = setTimeout(() => {
                loadFolders(query);
                loadFiles(currentPath, query);
            }, 300);
        });
    }

    // Initialize Dashboard data
    loadConnectors();
});

