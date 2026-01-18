// src/components/LoginModal.js - SIMPLIFIED (using standard axios)
import React, { useState } from 'react';
import axios from 'axios';

const LoginModal = ({ isOpen, onClose, onLoginSuccess }) => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [registerData, setRegisterData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    if (isRegistering) {
      setRegisterData(prev => ({ ...prev, [name]: value }));
    } else {
      setCredentials(prev => ({ ...prev, [name]: value }));
    }
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
        password: credentials.password,
        remember_me: rememberMe
      });

      console.log('📨 Login response:', response.data);

      if (response.data.success) {
        const { token, user: userData } = response.data;
        
        // Store with CONSISTENT keys that App.js expects
        const storage = rememberMe ? localStorage : sessionStorage;
        storage.setItem('auth_token', token);
        storage.setItem('user', JSON.stringify(userData));
        
        // Set axios header for future requests
        axios.defaults.headers.common['Authorization'] = `Token ${token}`;
        
        console.log('✅ Login successful, stored in', rememberMe ? 'localStorage' : 'sessionStorage');
        
        onLoginSuccess(userData);
        
        // Reset form
        setCredentials({ username: '', password: '' });
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

  const handleRegister = async (e) => {
    e.preventDefault();
    
    const { username, email, password, confirmPassword, first_name, last_name } = registerData;
    
    if (!username || !email || !password || !confirmPassword) {
      setError('Please fill all required fields');
      return;
    }
    
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);
    setError('');

    try {
      console.log('📝 Attempting registration...');
      
      const response = await axios.post('http://127.0.0.1:8000/api/auth/register/', {
        username,
        email,
        password,
        first_name,
        last_name
      });

      if (response.data.success) {
        const { token, user: newUser } = response.data;
        
        // Auto-login after registration
        localStorage.setItem('auth_token', token);
        localStorage.setItem('user', JSON.stringify(newUser));
        axios.defaults.headers.common['Authorization'] = `Token ${token}`;
        
        console.log('✅ Registration successful');
        
        onLoginSuccess(newUser);
        
        // Reset form
        setRegisterData({
          username: '',
          email: '',
          password: '',
          confirmPassword: '',
          first_name: '',
          last_name: ''
        });
      } else {
        setError(response.data.message || 'Registration failed');
      }
    } catch (err) {
      console.error('❌ Registration error:', err);
      
      let errorMsg = 'Registration failed. Please try again.';
      
      if (!err.response) {
        errorMsg = 'Cannot connect to server. Is the backend running?';
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
    setRegisterData({
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
      first_name: '',
      last_name: ''
    });
    setError('');
    setIsRegistering(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content login-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isRegistering ? 'Create Account' : 'Login'}</h2>
          <button onClick={handleClose} className="modal-close-button">×</button>
        </div>

        {error && (
          <div className="alert-error" style={{
            padding: '12px',
            marginBottom: '16px',
            backgroundColor: '#fee',
            color: '#c33',
            borderRadius: '4px',
            border: '1px solid #fcc'
          }}>
            {error}
          </div>
        )}

        {!isRegistering ? (
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                name="username"
                value={credentials.username}
                onChange={handleInputChange}
                placeholder="Enter username"
                disabled={loading}
                autoComplete="username"
              />
            </div>

            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                name="password"
                value={credentials.password}
                onChange={handleInputChange}
                placeholder="Enter password"
                disabled={loading}
                autoComplete="current-password"
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  disabled={loading}
                  style={{ marginRight: '8px' }}
                />
                Remember me
              </label>
            </div>

            <button type="submit" disabled={loading} className="button button-primary">
              {loading ? 'Signing in...' : 'Sign In'}
            </button>

            <div style={{ textAlign: 'center', marginTop: '16px' }}>
              <button
                type="button"
                onClick={() => {
                  setIsRegistering(true);
                  setError('');
                }}
                disabled={loading}
                style={{ background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', textDecoration: 'underline' }}
              >
                Need an account? Sign up
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div className="form-group">
                <label>First Name</label>
                <input
                  type="text"
                  name="first_name"
                  value={registerData.first_name}
                  onChange={handleInputChange}
                  placeholder="First name"
                  disabled={loading}
                />
              </div>
              <div className="form-group">
                <label>Last Name</label>
                <input
                  type="text"
                  name="last_name"
                  value={registerData.last_name}
                  onChange={handleInputChange}
                  placeholder="Last name"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Username *</label>
              <input
                type="text"
                name="username"
                value={registerData.username}
                onChange={handleInputChange}
                placeholder="Choose username"
                required
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label>Email *</label>
              <input
                type="email"
                name="email"
                value={registerData.email}
                onChange={handleInputChange}
                placeholder="Enter email"
                required
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label>Password *</label>
              <input
                type="password"
                name="password"
                value={registerData.password}
                onChange={handleInputChange}
                placeholder="Create password (min 6 characters)"
                required
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label>Confirm Password *</label>
              <input
                type="password"
                name="confirmPassword"
                value={registerData.confirmPassword}
                onChange={handleInputChange}
                placeholder="Confirm password"
                required
                disabled={loading}
              />
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                onClick={() => {
                  setIsRegistering(false);
                  setError('');
                }}
                className="button button-secondary"
                disabled={loading}
                style={{ flex: 1 }}
              >
                Back to Login
              </button>
              <button
                type="submit"
                disabled={loading}
                className="button button-primary"
                style={{ flex: 1 }}
              >
                {loading ? 'Creating Account...' : 'Sign Up'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default LoginModal;