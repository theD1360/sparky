import React from 'react';
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
} from '@mui/material';
import {
  Close as CloseIcon,
  Person as PersonIcon,
  Email as EmailIcon,
  CalendarToday as CalendarIcon,
} from '@mui/icons-material';

/**
 * User profile modal - shows user information and preferences
 * @param {boolean} isOpen - Whether modal is open
 * @param {function} onClose - Callback to close modal
 */
function UserModal({ isOpen, onClose }) {
  // Get user ID from localStorage
  const userId = localStorage.getItem('user_id') || 'Unknown';
  const userIdShort = userId.substring(0, 8);

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
            <PersonIcon fontSize="large" />
          </Avatar>
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
            Sparky User
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            sparky.user@badrobot.ai
          </Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* User Information */}
        <List dense>
          <ListItem>
            <PersonIcon sx={{ mr: 2, color: 'text.secondary' }} />
            <ListItemText
              primary="User ID"
              secondary={userIdShort}
              primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
              secondaryTypographyProps={{ variant: 'body1' }}
            />
          </ListItem>

          <ListItem>
            <EmailIcon sx={{ mr: 2, color: 'text.secondary' }} />
            <ListItemText
              primary="Email"
              secondary="sparky.user@badrobot.ai"
              primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
              secondaryTypographyProps={{ variant: 'body1' }}
            />
          </ListItem>

          <ListItem>
            <CalendarIcon sx={{ mr: 2, color: 'text.secondary' }} />
            <ListItemText
              primary="Member Since"
              secondary="November 2025"
              primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
              secondaryTypographyProps={{ variant: 'body1' }}
            />
          </ListItem>
        </List>

        <Divider sx={{ my: 2 }} />

        {/* Placeholder for future features */}
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            bgcolor: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.2)',
          }}
        >
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            👤 Profile customization features coming soon!
          </Typography>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button onClick={onClose} variant="contained" fullWidth>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default UserModal;

