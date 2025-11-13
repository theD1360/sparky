import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App';
import { theme } from './styles/theme';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/chat" element={<App />} />
          <Route path="/chat/:chatId" element={<App />} />
        </Routes>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);

reportWebVitals();
