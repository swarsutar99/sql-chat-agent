// API Configuration
const API_BASE_URL = 'http://localhost:8001/api';

// Get auth token
function getAuthToken() {
    return localStorage.getItem('vanna_token');
}

// Get current user
function getCurrentUser() {
    const userStr = localStorage.getItem('vanna_user');
    return userStr ? JSON.parse(userStr) : null;
}

// Chat API - Updated for proxy
class ChatAPI {
    constructor() {
        this.eventSource = null;
        this.conversationId = null;
        this.messageCallbacks = [];
        this.errorCallbacks = [];
        this.completeCallbacks = [];
    }
    
    // Send message via SSE (through proxy)
    async sendMessage(message, conversationId = null) {
        const token = getAuthToken();
        if (!token) throw new Error('Not authenticated');
    
        this.conversationId =
            conversationId || `conv_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    
        const response = await fetch(`${API_BASE_URL}/vanna/v2/chat_sse`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message,
                conversation_id: this.conversationId
            })
        });
    
        if (!response.ok) {
            throw new Error('Request failed');
        }
    
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalText = '';
        let sqlQuery = '';
    
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
    
            buffer += decoder.decode(value, { stream: true });
            
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';
    
            for (const event of events) {
                if (!event.trim()) continue;
                
                if (event.trim() === 'data: [DONE]') {
                    // Show final answer
                    if (finalText) {
                        this.messageCallbacks.forEach(cb => cb({
                            type: 'text',
                            content: finalText
                        }));
                    }
                    
                    // Show SQL if available
                    if (sqlQuery) {
                        this.messageCallbacks.forEach(cb => cb({
                            type: 'sql',
                            content: sqlQuery
                        }));
                    }
                    
                    this.completeCallbacks.forEach(cb => cb({
                        type: 'complete',
                        conversation_id: this.conversationId
                    }));
                    return;
                }
                
                if (event.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(event.substring(6));
                        
                        // Capture final text response
                        if (data.simple?.type === 'text' && data.simple?.text) {
                            finalText = data.simple.text;
                        }
                        
                        // Capture SQL query
                        if (data.rich?.type === 'status_card' && data.rich?.data?.metadata?.sql) {
                            sqlQuery = data.rich.data.metadata.sql;
                        }
                        
                    } catch (e) {
                        // Ignore parse errors
                    }
                }
            }
        }
    }
    
    // Helper to filter which events to display
    shouldDisplayEvent(data) {
        // Show text responses
        if (data.simple?.type === 'text' && data.simple?.text) {
            return true;
        }
        
        // Show SQL queries
        if (data.rich?.type === 'status_card' && data.rich?.data?.metadata?.sql) {
            return true;
        }
        
        // Show errors
        if (data.rich?.type === 'notification' && data.rich?.data?.level === 'error') {
            return true;
        }
        
        // Show success notifications
        if (data.rich?.type === 'notification' && data.rich?.data?.level === 'success') {
            return true;
        }
        
        return false;
    }
    
    
    // Register callbacks
    onMessage(callback) {
        this.messageCallbacks.push(callback);
    }
    
    onError(callback) {
        this.errorCallbacks.push(callback);
    }
    
    onComplete(callback) {
        this.completeCallbacks.push(callback);
    }
    
    // Close connection
    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
    
    // Alternative: Use polling endpoint
    async sendMessagePolling(message, conversationId = null) {
        const token = getAuthToken();
        if (!token) throw new Error('Not authenticated');
        
        const response = await fetch(`${API_BASE_URL}/vanna/v2/chat_poll`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId || `conv_${Date.now()}`
            })
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        return await response.json();
    }
}

// Export API instance
window.chatAPI = new ChatAPI();