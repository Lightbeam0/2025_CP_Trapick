// src/components/LoginModal.js - SIMPLIFIED VERSION WITHOUT SIGN UP
import React, { useState } from 'react';
import axios from 'axios';

const LoginModal = ({ isOpen, onClose, onLoginSuccess }) => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setCredentials(prev => ({ ...prev, [name]: value }));
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    
    if (!credentials.username || !credentials.password) {
      setError('Please enter both username and password');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('🔐 Attempting login...');
      
      const response = await axios.post('http://127.0.0.1:8000/api/auth/login/', {
        username: credentials.username,
        password: credentials.password
      });

      console.log('📨 Login response:', response.data);

      if (response.data.success) {
        const { token, user: userData } = response.data;
        
        // Store in localStorage for persistent login
        localStorage.setItem('auth_token', token);
        localStorage.setItem('user', JSON.stringify(userData));
        
        // Set axios header for future requests
        axios.defaults.headers.common['Authorization'] = `Token ${token}`;
        
        console.log('✅ Login successful');
        
        onLoginSuccess(userData);
        
        // Reset form
        setCredentials({ username: '', password: '' });
        onClose();
      } else {
        setError(response.data.message || 'Login failed');
      }
    } catch (err) {
      console.error('❌ Login error:', err);
      
      let errorMsg = 'Login failed. Please try again.';
      
      if (!err.response) {
        errorMsg = 'Cannot connect to server. Is the backend running at http://127.0.0.1:8000?';
      } else if (err.response.status === 401) {
        errorMsg = 'Invalid username or password';
      } else if (err.response?.data?.message) {
        errorMsg = err.response.data.message;
      }
      
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setCredentials({ username: '', password: '' });
    setError('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content login-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Login to TRAPICK</h2>
          <button onClick={handleClose} className="modal-close-button">×</button>
        </div>

        {error && (
          <div className="alert-error">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={credentials.username}
              onChange={handleInputChange}
              placeholder="Enter username"
              disabled={loading}
              autoComplete="username"
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={credentials.password}
              onChange={handleInputChange}
              placeholder="Enter password"
              disabled={loading}
              autoComplete="current-password"
              className="form-input"
            />
          </div>

          <button 
            type="submit" 
            disabled={loading} 
            className="button button-primary login-button"
          >
            {loading ? (
              <>
                <span className="spinner"></span>
                Signing in...
              </>
            ) : 'Sign In'}
          </button>

          <div className="login-footer">
            <p className="login-note">
              Contact the administrator for account creation
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginModal;