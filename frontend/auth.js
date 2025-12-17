// API Configuration
const API_BASE_URL = 'http://localhost:8001/api';
let currentUser = null;
let currentUserType = 'admin';

// DOM Elements
let emailInput, passwordInput, emailLabel, emailHelper, loginText;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('email')) {
        // Login page elements
        emailInput = document.getElementById('email');
        passwordInput = document.getElementById('password');
        emailLabel = document.getElementById('email-label');
        emailHelper = document.getElementById('email-helper');
        loginText = document.getElementById('login-text');
        
        // Check if already logged in
        checkAuth();
    }
});

// Switch between admin/user tabs
function switchTab(tab) {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(t => t.classList.remove('active'));
    
    const activeTab = document.querySelector(`.tab-btn[onclick*="${tab}"]`);
    if (activeTab) activeTab.classList.add('active');
    
    currentUserType = tab;
    
    // Update form labels
    if (emailLabel && emailHelper && loginText) {
        if (tab === 'admin') {
            emailLabel.textContent = 'Admin Email';
            emailHelper.textContent = 'Use your existing admin email from MySQL admins table';
            loginText.textContent = 'Login as Admin';
            emailInput.placeholder = 'admin@definelabs.com';
        } else {
            emailLabel.textContent = 'Username or Email';
            emailHelper.textContent = 'Use username or email from users table';
            loginText.textContent = 'Login as User';
            emailInput.placeholder = 'user_of_company_old or email';
        }
    }
}

// Load demo credentials
function loadDemo(type) {
    if (type === 'admin') {
        emailInput.value = 'admin@definelabs.com';
        currentUserType = 'admin';
        switchTab('admin');
    } else {
        emailInput.value = 'user_of_company_old';
        currentUserType = 'user';
        switchTab('user');
    }
    passwordInput.value = '';
    passwordInput.focus();
    
    showMessage('Demo credentials loaded. Please enter your actual password.', 'info');
}

// Toggle password visibility
function togglePassword() {
    const type = passwordInput.type === 'password' ? 'text' : 'password';
    passwordInput.type = type;
    const icon = document.querySelector('.toggle-password i');
    icon.className = type === 'password' ? 'fas fa-eye' : 'fas fa-eye-slash';
}

// Show message
function showMessage(message, type = 'error') {
    const errorDiv = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    
    if (!errorDiv || !errorText) return;
    
    errorText.textContent = message;
    errorDiv.className = type === 'error' ? 'error-message' : 'error-message info';
    errorDiv.classList.remove('hidden');
    
    if (type !== 'error') {
        setTimeout(() => {
            errorDiv.classList.add('hidden');
        }, 3000);
    }
}

// Login function
async function login() {
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    
    if (!email || !password) {
        showMessage('Please enter both email/username and password');
        return;
    }
    
    // Show loading
    const loginBtn = document.querySelector('.login-btn');
    const originalText = loginBtn.innerHTML;
    loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Authenticating...';
    loginBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                password: password,
                user_type: currentUserType
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }
        
        // Store authentication
        localStorage.setItem('vanna_token', data.access_token);
        localStorage.setItem('vanna_user', JSON.stringify(data.user));
        localStorage.setItem('vanna_user_type', currentUserType);
        
        // Redirect to chat
        window.location.href = 'chat.html';
        
    } catch (error) {
        showMessage(error.message);
    } finally {
        loginBtn.innerHTML = originalText;
        loginBtn.disabled = false;
    }
}

// Check if already authenticated
function checkAuth() {
    const token = localStorage.getItem('vanna_token');
    if (token && window.location.pathname.includes('index.html')) {
        // Already logged in, redirect to chat
        window.location.href = 'chat.html';
    }
}

// Check token validity (for chat page)
async function validateToken() {
    const token = localStorage.getItem('vanna_token');
    if (!token) {
        window.location.href = 'index.html';
        return null;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Invalid token');
        }
        
        const userData = await response.json();
        currentUser = userData;
        return userData;
    } catch (error) {
        localStorage.removeItem('vanna_token');
        localStorage.removeItem('vanna_user');
        localStorage.removeItem('vanna_user_type');
        window.location.href = 'index.html';
        return null;
    }
}

// Logout function (used in chat.js)
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        localStorage.removeItem('vanna_token');
        localStorage.removeItem('vanna_user');
        localStorage.removeItem('vanna_user_type');
        window.location.href = 'index.html';
    }
}