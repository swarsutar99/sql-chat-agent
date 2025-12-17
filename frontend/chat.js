// Global variables
let currentConversation = null;
let messages = [];
let isLoading = false;

// DOM Elements
let messageInput, sendBtn, chatMessages, userInfo, userName, userRole;
let conversationList, conversationTitle, messageCount;
let resultsContent, sqlContent, chartContainer;
let loadingOverlay, loadingDetails;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    if (!document.getElementById('message-input')) return;
    
    // Get DOM elements
    initializeElements();
    
    // Check authentication
    const user = await validateToken();
    if (!user) return;
    
    // Setup user info
    setupUserInfo(user);
    
    // Load conversations
    loadConversations();
    
    // Setup event listeners
    setupEventListeners();
    
    // Setup chat API callbacks
    setupChatCallbacks();
});

// Initialize DOM elements
function initializeElements() {
    messageInput = document.getElementById('message-input');
    sendBtn = document.getElementById('send-btn');
    chatMessages = document.getElementById('chat-messages');
    userInfo = document.getElementById('user-info');
    userName = document.getElementById('user-name');
    userRole = document.getElementById('user-role');
    conversationList = document.getElementById('conversation-list');
    conversationTitle = document.getElementById('conversation-title');
    messageCount = document.getElementById('message-count');
    resultsContent = document.getElementById('results-content');
    sqlContent = document.getElementById('sql-content');
    chartContainer = document.getElementById('chart-container');
    loadingOverlay = document.getElementById('loading-overlay');
    loadingDetails = document.getElementById('loading-details');
}

// Setup user info
function setupUserInfo(userData) {
    const storedUser = getCurrentUser();
    const user = userData || storedUser;
    
    if (user) {
        userName.textContent = user.name || user.email || user.username || 'User';
        userRole.textContent = user.role === 'admin' ? 'Administrator' : 'Regular User';
        
        // Add role badge color
        if (user.role.includes('admin')) {
            userRole.style.background = '#eef2ff';
            userRole.style.color = '#4f46e5';
        }
    }
}

// Setup event listeners
function setupEventListeners() {
    // Send button
    sendBtn.addEventListener('click', sendMessage);
    
    // Enter key in input
    messageInput.addEventListener('keydown', handleKeyPress);
    
    // Input focus
    messageInput.addEventListener('focus', function() {
        this.style.background = 'white';
    });
    
    // Input blur
    messageInput.addEventListener('blur', function() {
        this.style.background = '#f9fafb';
    });
}

// Setup chat API callbacks
function setupChatCallbacks() {
    window.chatAPI.onMessage((data) => {
        handleStreamingMessage(data);
    });
    
    window.chatAPI.onError((error) => {
        showError(error.content || 'An error occurred');
        hideLoading();
    });
    
    window.chatAPI.onComplete((data) => {
        currentConversation = data.conversation_id;
        updateConversationTitle();
        hideLoading();
        loadConversations();
    });
}

// Handle key press in input
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        if (!isLoading) {
            sendMessage();
        }
    }
}

// Send message
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message || isLoading) return;
    
    // Clear input
    messageInput.value = '';
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Show loading
    showLoading('AI is processing your query...');
    
    // Send to API
    try {
        await window.chatAPI.sendMessage(message, currentConversation);
    } catch (error) {
        showError(error.message);
        hideLoading();
    }
}

// Handle streaming message
function handleStreamingMessage(data) {
    switch (data.type) {
        case 'thinking':
            updateLoadingDetails(data.content);
            addMessage(data.content, 'thinking');
            break;
            
        case 'sql':
            updateLoadingDetails('Executing SQL query...');
            showSQL(data.content);
            break;
            
        case 'success':
            addMessage(data.content, 'ai');
            showResults(data.content);
            updateLoadingDetails('Rendering results...');
            break;
            
        case 'info':
            addMessage(data.content, 'ai');
            break;
    }
}

// Add message to chat
function addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    let icon = '';
    if (type === 'thinking') {
        icon = '<i class="fas fa-spinner fa-spin"></i>';
    } else if (type === 'user') {
        icon = '<i class="fas fa-user"></i> ';
    } else if (type === 'ai') {
        icon = '<i class="fas fa-robot"></i> ';
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">${icon}${escapeHtml(content)}</div>
        <div class="message-time">${time}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Update message count
    messages.push({ content, type, time });
    updateMessageCount();
    
    // Hide welcome message if first message
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage && messages.length === 1) {
        welcomeMessage.style.display = 'none';
    }
}

// Show SQL in panel
function showSQL(sql) {
    switchPanel('sql');
    sqlContent.textContent = sql;
    sqlContent.classList.remove('hidden');
    document.querySelector('#sql-panel .empty-state').classList.add('hidden');
}

// Show results in panel
function showResults(results) {
    switchPanel('results');
    
    // Try to parse as JSON for table display
    try {
        const data = JSON.parse(results);
        if (Array.isArray(data)) {
            displayTable(data);
        } else {
            resultsContent.innerHTML = `<div class="text-result">${escapeHtml(results)}</div>`;
        }
    } catch {
        // Not JSON, display as text
        resultsContent.innerHTML = `<div class="text-result">${escapeHtml(results)}</div>`;
    }
    
    resultsContent.classList.remove('hidden');
    document.querySelector('#results-panel .empty-state').classList.add('hidden');
}

// Display data as table
function displayTable(data) {
    if (!data.length) {
        resultsContent.innerHTML = '<div class="text-result">No data found</div>';
        return;
    }
    
    const headers = Object.keys(data[0]);
    let html = '<table class="data-table"><thead><tr>';
    
    headers.forEach(header => {
        html += `<th>${escapeHtml(header)}</th>`;
    });
    
    html += '</tr></thead><tbody>';
    
    data.forEach(row => {
        html += '<tr>';
        headers.forEach(header => {
            const value = row[header];
            html += `<td>${escapeHtml(String(value))}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    resultsContent.innerHTML = html;
}

// Switch panel tabs
function switchPanel(panelName) {
    // Update tabs
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    document.querySelectorAll('.panel-tab').forEach(tab => {
        if (tab.textContent.includes(panelName.charAt(0).toUpperCase() + panelName.slice(1))) {
            tab.classList.add('active');
        }
    });
    
    // Update content
    document.querySelectorAll('.panel-section').forEach(section => {
        section.classList.remove('active');
    });
    
    document.getElementById(`${panelName}-panel`).classList.add('active');
}

// Load conversations
async function loadConversations() {
    try {
        const conversations = await window.chatAPI.getConversations();
        
        if (conversations.length === 0) {
            conversationList.innerHTML = '<div class="empty-conversations">No conversations yet</div>';
            return;
        }
        
        let html = '';
        conversations.forEach((conv, index) => {
            const isActive = conv.id === currentConversation;
            const preview = conv.last_message ? conv.last_message.substring(0, 30) + '...' : 'Empty conversation';
            const date = conv.timestamp ? new Date(conv.timestamp).toLocaleDateString() : 'Recent';
            
            html += `
                <div class="conversation-item ${isActive ? 'active' : ''}" 
                     onclick="loadConversation('${conv.id}')">
                    <div>
                        <div class="conversation-title">Chat ${index + 1}</div>
                        <div class="conversation-preview">${escapeHtml(preview)}</div>
                    </div>
                    <div class="conversation-date">${date}</div>
                </div>
            `;
        });
        
        conversationList.innerHTML = html;
    } catch (error) {
        console.error('Error loading conversations:', error);
    }
}

// Load conversation
function loadConversation(conversationId) {
    currentConversation = conversationId;
    // In a real implementation, you would fetch conversation messages
    // For now, just update the UI
    updateConversationTitle();
    showMessage('Loading conversation...', 'info');
}

// New chat
function newChat() {
    if (messages.length > 0 && !confirm('Start a new chat? Current chat will be cleared.')) {
        return;
    }
    
    currentConversation = null;
    messages = [];
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">
                <i class="fas fa-database"></i>
            </div>
            <h3>Welcome to Vanna AI Assistant!</h3>
            <p>Ask questions about your database in natural language:</p>
            <div class="example-queries">
                <span class="example-tag" onclick="setExample(this)">"Show me all tables"</span>
                <span class="example-tag" onclick="setExample(this)">"What's the total profit this month?"</span>
                <span class="example-tag" onclick="setExample(this)">"List top 10 users by balance"</span>
                <span class="example-tag" onclick="setExample(this)">"Today's settled bets"</span>
            </div>
        </div>
    `;
    
    updateConversationTitle();
    updateMessageCount();
    
    // Clear panels
    resultsContent.innerHTML = '';
    resultsContent.classList.add('hidden');
    sqlContent.textContent = '';
    sqlContent.classList.add('hidden');
    chartContainer.innerHTML = '';
    chartContainer.classList.add('hidden');
    
    document.querySelectorAll('.empty-state').forEach(el => {
        el.classList.remove('hidden');
    });
}

// Set example query
function setExample(element) {
    messageInput.value = element.textContent.replace(/"/g, '').trim();
    messageInput.focus();
}

// Set query from quick buttons
function setQuery(button) {
    messageInput.value = button.textContent.replace(/^.+\s/, '').trim();
    messageInput.focus();
}

// Update conversation title
function updateConversationTitle() {
    if (currentConversation) {
        conversationTitle.textContent = `Chat ${currentConversation.substring(0, 8)}...`;
    } else {
        conversationTitle.textContent = 'New Chat';
    }
}

// Update message count
function updateMessageCount() {
    const count = messages.length;
    messageCount.textContent = `${count} message${count !== 1 ? 's' : ''}`;
}

// Show loading overlay
function showLoading(message) {
    isLoading = true;
    sendBtn.disabled = true;
    messageInput.disabled = true;
    
    if (loadingOverlay && loadingDetails) {
        loadingDetails.innerHTML = `<i class="fas fa-brain"></i> ${message}`;
        loadingOverlay.classList.remove('hidden');
    }
}

// Update loading details
function updateLoadingDetails(message) {
    if (loadingDetails) {
        loadingDetails.innerHTML = `<i class="fas fa-brain"></i> ${message}`;
    }
}

// Hide loading overlay
function hideLoading() {
    isLoading = false;
    sendBtn.disabled = false;
    messageInput.disabled = false;
    
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
    }
}

// Show error
function showError(message) {
    addMessage(`Error: ${message}`, 'ai');
    hideLoading();
}

// Copy results
function copyResults() {
    const activePanel = document.querySelector('.panel-section.active');
    let text = '';
    
    if (activePanel.id === 'results-panel') {
        text = resultsContent.innerText;
    } else if (activePanel.id === 'sql-panel') {
        text = sqlContent.innerText;
    }
    
    if (text) {
        navigator.clipboard.writeText(text).then(() => {
            showMessage('Copied to clipboard!', 'info');
        });
    }
}

// Download CSV
function downloadCSV() {
    const table = resultsContent.querySelector('table');
    if (!table) {
        showMessage('No table data to download', 'info');
        return;
    }
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
        const rowData = [];
        row.querySelectorAll('th, td').forEach(cell => {
            rowData.push(`"${cell.innerText.replace(/"/g, '""')}"`);
        });
        csv.push(rowData.join(','));
    });
    
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `vanna-query-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    
    URL.revokeObjectURL(url);
}

// Refresh data
function refreshData() {
    if (messages.length > 0) {
        const lastUserMessage = messages.filter(m => m.type === 'user').pop();
        if (lastUserMessage) {
            sendMessage(lastUserMessage.content);
        }
    }
}

// Show temporary message
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `temporary-message ${type}`;
    messageDiv.textContent = message;
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'info' ? '#10b981' : '#ef4444'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 1000;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => messageDiv.remove(), 300);
    }, 3000);
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Utility: Add CSS animations
function addAnimationStyles() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}

// Initialize animations
addAnimationStyles();