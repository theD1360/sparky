import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Container,
  Stack,
  Card,
  CardContent,
  Grid,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Chat as ChatIcon,
  Code as CodeIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Psychology as PsychologyIcon,
  AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';

function Home() {
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const features = [
    {
      icon: <ChatIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'Intelligent Conversations',
      description: 'Engage in natural, context-aware conversations powered by advanced AI.',
    },
    {
      icon: <CodeIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'Tool Integration',
      description: 'Access a wide range of tools and capabilities through simple commands.',
    },
    {
      icon: <SpeedIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'Fast & Responsive',
      description: 'Real-time WebSocket connections for instant, seamless interactions.',
    },
    {
      icon: <MemoryIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'Context Awareness',
      description: 'Maintains conversation history and context across multiple sessions.',
    },
    {
      icon: <PsychologyIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'Smart Assistance',
      description: 'Get help with tasks, questions, and problem-solving in real-time.',
    },
    {
      icon: <AutoAwesomeIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'Rich Features',
      description: 'File uploads, autocomplete, prompts, and resources at your fingertips.',
    },
  ];

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Hero Section */}
      <Container maxWidth="lg" sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', py: 8 }}>
        <Stack spacing={6} alignItems="center" textAlign="center">
          {/* Logo and Title */}
          <Box>
            <Box
              component="img"
              src="/robot-logo.svg"
              alt="Sparky"
              sx={{
                height: isMobile ? 80 : 120,
                width: isMobile ? 80 : 120,
                mb: 3,
                animation: 'float 3s ease-in-out infinite',
                '@keyframes float': {
                  '0%, 100%': {
                    transform: 'translateY(0px)',
                  },
                  '50%': {
                    transform: 'translateY(-10px)',
                  },
                },
              }}
            />
            <Typography
              variant={isMobile ? 'h3' : 'h2'}
              sx={{
                fontWeight: 700,
                color: 'text.primary',
                mb: 2,
                background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Welcome to Sparky Studio
            </Typography>
            <Typography
              variant={isMobile ? 'h6' : 'h5'}
              sx={{
                color: 'text.secondary',
                fontWeight: 300,
                maxWidth: '800px',
                mx: 'auto',
              }}
            >
              Your intelligent AI assistant for conversations, problem-solving, and productivity
            </Typography>
          </Box>

          {/* CTA Button */}
          <Button
            variant="contained"
            size="large"
            startIcon={<ChatIcon />}
            onClick={() => navigate('/chat')}
            sx={{
              px: 6,
              py: 2,
              fontSize: '1.125rem',
              fontWeight: 600,
              borderRadius: 3,
              bgcolor: 'primary.main',
              background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
              boxShadow: '0 8px 24px rgba(59, 130, 246, 0.4)',
              transition: 'all 0.3s ease',
              '&:hover': {
                boxShadow: '0 12px 32px rgba(59, 130, 246, 0.6)',
                transform: 'translateY(-2px)',
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              },
            }}
          >
            Start Chatting
          </Button>

          {/* Features Grid */}
          <Box sx={{ width: '100%', mt: 8 }}>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 600,
                color: 'text.primary',
                mb: 4,
                textAlign: 'center',
              }}
            >
              What Sparky Can Do
            </Typography>
            <Grid container spacing={3} justifyContent="center">
              {features.map((feature, index) => (
                <Grid item xs={12} sm={6} md={4} key={index}>
                  <Card
                    sx={{
                      height: '100%',
                      bgcolor: 'rgba(17, 24, 39, 0.6)',
                      backdropFilter: 'blur(10px)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: 3,
                      transition: 'all 0.3s ease',
                      '&:hover': {
                        transform: 'translateY(-4px)',
                        boxShadow: '0 12px 24px rgba(59, 130, 246, 0.2)',
                        border: '1px solid rgba(59, 130, 246, 0.3)',
                      },
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Box sx={{ mb: 2 }}>{feature.icon}</Box>
                      <Typography
                        variant="h6"
                        sx={{
                          fontWeight: 600,
                          color: 'text.primary',
                          mb: 1,
                        }}
                      >
                        {feature.title}
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          color: 'text.secondary',
                          lineHeight: 1.6,
                        }}
                      >
                        {feature.description}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>

          {/* Additional CTA */}
          <Box
            sx={{
              mt: 6,
              p: 4,
              borderRadius: 3,
              bgcolor: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              maxWidth: '700px',
            }}
          >
            <Typography
              variant="h5"
              sx={{
                fontWeight: 600,
                color: 'text.primary',
                mb: 2,
              }}
            >
              Ready to Get Started?
            </Typography>
            <Typography
              variant="body1"
              sx={{
                color: 'text.secondary',
                mb: 3,
              }}
            >
              Start a conversation with Sparky and experience the power of AI-assisted productivity.
            </Typography>
            <Button
              variant="outlined"
              size="large"
              startIcon={<ChatIcon />}
              onClick={() => navigate('/chat')}
              sx={{
                px: 4,
                py: 1.5,
                borderRadius: 2,
                borderColor: 'primary.main',
                color: 'primary.main',
                fontWeight: 600,
                '&:hover': {
                  borderColor: 'primary.light',
                  bgcolor: 'rgba(59, 130, 246, 0.1)',
                },
              }}
            >
              Launch Chat Interface
            </Button>
          </Box>
        </Stack>
      </Container>

      {/* Footer */}
      <Box
        sx={{
          py: 3,
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          textAlign: 'center',
        }}
      >
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Sparky Studio - Powered by BadRobot AI
        </Typography>
      </Box>
    </Box>
  );
}

export default Home;

