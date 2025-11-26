import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Avatar,
  Divider,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Chip,
  Alert,
  TextField,
  Collapse,
} from '@mui/material';
import {
  Close as CloseIcon,
  Person as PersonIcon,
  Email as EmailIcon,
  CalendarToday as CalendarIcon,
  Logout as LogoutIcon,
  Verified as VerifiedIcon,
  Cancel as CancelIcon,
  Lock as LockIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { useAuth } from '../auth/AuthProvider';
import { useNavigate } from 'react-router-dom';

/**
 * User profile modal - shows user information and preferences
 * @param {boolean} isOpen - Whether modal is open
 * @param {function} onClose - Callback to close modal
 */
function UserModal({ isOpen, onClose }) {
  const { user, logout, isAuthenticated, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  const [showPasswordChange, setShowPasswordChange] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [passwordError, setPasswordError] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      logout();
      onClose();
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setLoggingOut(false);
    }
  };

  if (!isAuthenticated || !user) {
    return null;
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
    } catch {
      return 'N/A';
    }
  };

  const getInitials = (username) => {
    if (!username) return 'U';
    return username.substring(0, 2).toUpperCase();
  };

  const handlePasswordChange = async () => {
    setPasswordError('');
    
    // Validation
    if (!passwordForm.currentPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
      setPasswordError('All fields are required');
      return;
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('New passwords do not match');
      return;
    }

    if (passwordForm.newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters long');
      return;
    }

    setChangingPassword(true);
    try {
      const response = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({
          current_password: passwordForm.currentPassword,
          new_password: passwordForm.newPassword,
        }),
      });

      if (response.ok) {
        // Success - reset form and close
        setPasswordForm({
          currentPassword: '',
          newPassword: '',
          confirmPassword: '',
        });
        setShowPasswordChange(false);
        setPasswordError('');
        alert('Password changed successfully');
      } else {
        const error = await response.json();
        setPasswordError(error.detail || 'Failed to change password');
      }
    } catch (error) {
      console.error('Password change error:', error);
      setPasswordError('Network error. Please try again.');
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#111827',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 3,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          User Profile
        </Typography>
        <IconButton onClick={onClose} size="small" sx={{ color: 'text.secondary' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {/* Profile Header */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3, mt: 2 }}>
          <Avatar
            sx={{
              width: 80,
              height: 80,
              bgcolor: 'primary.main',
              mb: 2,
              fontSize: '2rem',
            }}
          >
            {getInitials(user.username)}
          </Avatar>
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
            {user.username}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            {user.email}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'center' }}>
            {user.roles && user.roles.map((role) => (
              <Chip
                key={role}
                label={role}
                size="small"
                color={role === 'admin' ? 'primary' : 'default'}
                sx={{ textTransform: 'capitalize' }}
              />
            ))}
            {user.is_verified ? (
              <Chip
                icon={<VerifiedIcon />}
                label="Verified"
                size="small"
                color="success"
              />
            ) : (
              <Chip
                icon={<CancelIcon />}
                label="Unverified"
                size="small"
                color="default"
              />
            )}
            {!user.is_active && (
              <Chip
                label="Inactive"
                size="small"
                color="error"
              />
            )}
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* User Information */}
        <List dense>
          <ListItem>
            <PersonIcon sx={{ mr: 2, color: 'text.secondary' }} />
            <ListItemText
              primary="User ID"
              secondary={user.id.substring(0, 8) + '...'}
              primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
              secondaryTypographyProps={{ variant: 'body1', fontFamily: 'monospace' }}
            />
          </ListItem>

          <ListItem>
            <EmailIcon sx={{ mr: 2, color: 'text.secondary' }} />
            <ListItemText
              primary="Email"
              secondary={user.email}
              primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
              secondaryTypographyProps={{ variant: 'body1' }}
            />
          </ListItem>

          <ListItem>
            <CalendarIcon sx={{ mr: 2, color: 'text.secondary' }} />
            <ListItemText
              primary="Member Since"
              secondary={formatDate(user.created_at)}
              primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
              secondaryTypographyProps={{ variant: 'body1' }}
            />
          </ListItem>

          {user.last_login && (
            <ListItem>
              <CalendarIcon sx={{ mr: 2, color: 'text.secondary' }} />
              <ListItemText
                primary="Last Login"
                secondary={formatDate(user.last_login)}
                primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
                secondaryTypographyProps={{ variant: 'body1' }}
              />
            </ListItem>
          )}
        </List>

        <Divider sx={{ my: 2 }} />

        {/* Account Status */}
        {!user.is_active && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Your account is currently inactive. Please contact an administrator.
          </Alert>
        )}

        {!user.is_verified && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Your email address has not been verified yet.
          </Alert>
        )}

        {/* Password Change Section */}
        <Divider sx={{ my: 2 }} />
        <Box>
          <Button
            fullWidth
            variant="outlined"
            startIcon={<LockIcon />}
            endIcon={showPasswordChange ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            onClick={() => {
              setShowPasswordChange(!showPasswordChange);
              setPasswordError('');
              setPasswordForm({
                currentPassword: '',
                newPassword: '',
                confirmPassword: '',
              });
            }}
            sx={{ mb: 2 }}
          >
            Change Password
          </Button>

          <Collapse in={showPasswordChange}>
            <Box sx={{ p: 2, bgcolor: 'rgba(0, 0, 0, 0.1)', borderRadius: 2 }}>
              {passwordError && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {passwordError}
                </Alert>
              )}
              <TextField
                fullWidth
                label="Current Password"
                type="password"
                margin="normal"
                value={passwordForm.currentPassword}
                onChange={(e) =>
                  setPasswordForm({ ...passwordForm, currentPassword: e.target.value })
                }
                disabled={changingPassword}
              />
              <TextField
                fullWidth
                label="New Password"
                type="password"
                margin="normal"
                value={passwordForm.newPassword}
                onChange={(e) =>
                  setPasswordForm({ ...passwordForm, newPassword: e.target.value })
                }
                disabled={changingPassword}
                helperText="Must be at least 8 characters"
              />
              <TextField
                fullWidth
                label="Confirm New Password"
                type="password"
                margin="normal"
                value={passwordForm.confirmPassword}
                onChange={(e) =>
                  setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })
                }
                disabled={changingPassword}
              />
              <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                <Button
                  variant="contained"
                  onClick={handlePasswordChange}
                  disabled={changingPassword}
                  fullWidth
                >
                  {changingPassword ? 'Changing...' : 'Change Password'}
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => {
                    setShowPasswordChange(false);
                    setPasswordError('');
                    setPasswordForm({
                      currentPassword: '',
                      newPassword: '',
                      confirmPassword: '',
                    });
                  }}
                  disabled={changingPassword}
                >
                  Cancel
                </Button>
              </Box>
            </Box>
          </Collapse>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3, flexDirection: 'column', gap: 1 }}>
        <Button
          onClick={handleLogout}
          variant="outlined"
          color="error"
          fullWidth
          startIcon={<LogoutIcon />}
          disabled={loggingOut}
        >
          {loggingOut ? 'Logging out...' : 'Logout'}
        </Button>
        <Button onClick={onClose} variant="contained" fullWidth>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default UserModal;

