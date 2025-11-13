import React from 'react';
import { Box, Typography, LinearProgress, Stack } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';

function SplashScreen({ toolsLoading, totalTools }) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        width: '100vw',
        bgcolor: '#0a0e1a',
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 9999,
      }}
    >
      {/* Logo/Icon */}
      <Box
        component="img"
        src="/robot-logo.svg"
        alt="Sparky"
        sx={{
          height: 120,
          width: 120,
          mb: 4,
          animation: 'pulse 2s ease-in-out infinite',
          '@keyframes pulse': {
            '0%, 100%': {
              opacity: 1,
              transform: 'scale(1)',
            },
            '50%': {
              opacity: 0.7,
              transform: 'scale(1.05)',
            },
          },
        }}
      />

      {/* Title */}
      <Typography
        variant="h3"
        sx={{
          fontWeight: 700,
          color: 'primary.main',
          mb: 2,
        }}
      >
        Sparky Studio
      </Typography>

      {/* Subtitle */}
      <Typography
        variant="h6"
        sx={{
          color: 'text.secondary',
          mb: 6,
          fontWeight: 300,
        }}
      >
        Initializing Tools
      </Typography>

      {/* Progress Bar */}
      <Box sx={{ width: '400px', mb: 4 }}>
        <LinearProgress
          variant={totalTools > 0 ? "determinate" : "indeterminate"}
          value={totalTools > 0 ? (toolsLoading.filter(t => t.status === 'loaded').length / totalTools) * 100 : 0}
          sx={{
            height: 8,
            borderRadius: 4,
            bgcolor: 'rgba(59, 130, 246, 0.1)',
            '& .MuiLinearProgress-bar': {
              borderRadius: 4,
              bgcolor: 'primary.main',
            },
          }}
        />
        <Typography
          variant="caption"
          sx={{
            color: 'text.secondary',
            mt: 1,
            display: 'block',
            textAlign: 'center',
          }}
        >
          {totalTools > 0
            ? `${toolsLoading.filter(t => t.status === 'loaded').length} of ${totalTools} tools loaded`
            : 'Connecting...'}
        </Typography>
      </Box>

      {/* Tool Loading List */}
      <Box
        sx={{
          width: '500px',
          maxHeight: '300px',
          overflowY: 'auto',
          bgcolor: 'rgba(17, 24, 39, 0.6)',
          borderRadius: 2,
          p: 2,
          border: '1px solid rgba(255, 255, 255, 0.1)',
        }}
      >
        <Stack spacing={1.5}>
          {toolsLoading.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <HourglassEmptyIcon sx={{ color: 'text.secondary', mb: 1 }} />
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Connecting to server...
              </Typography>
            </Box>
          ) : (
            toolsLoading.map((tool, index) => (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  p: 1.5,
                  bgcolor: tool.status === 'loaded'
                    ? 'rgba(16, 185, 129, 0.1)'
                    : tool.status === 'error'
                    ? 'rgba(239, 68, 68, 0.1)'
                    : 'rgba(59, 130, 246, 0.1)',
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: tool.status === 'loaded'
                    ? 'rgba(16, 185, 129, 0.3)'
                    : tool.status === 'error'
                    ? 'rgba(239, 68, 68, 0.3)'
                    : 'rgba(59, 130, 246, 0.3)',
                  transition: 'all 0.3s ease',
                }}
              >
                {tool.status === 'loaded' && (
                  <CheckCircleIcon sx={{ color: '#10b981', fontSize: 20 }} />
                )}
                {tool.status === 'error' && (
                  <ErrorIcon sx={{ color: '#ef4444', fontSize: 20 }} />
                )}
                {tool.status === 'loading' && (
                  <Box
                    sx={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      border: '3px solid rgba(59, 130, 246, 0.3)',
                      borderTopColor: '#3b82f6',
                      animation: 'spin 1s linear infinite',
                      '@keyframes spin': {
                        '0%': { transform: 'rotate(0deg)' },
                        '100%': { transform: 'rotate(360deg)' },
                      },
                    }}
                  />
                )}
                <Box sx={{ flex: 1 }}>
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 600,
                      color: 'text.primary',
                    }}
                  >
                    {tool.tool_name}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                    }}
                  >
                    {tool.message}
                  </Typography>
                </Box>
              </Box>
            ))
          )}
        </Stack>
      </Box>
    </Box>
  );
}

export default SplashScreen;

