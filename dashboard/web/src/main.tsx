import { createRoot } from 'react-dom/client';
import { MantineProvider, createTheme } from '@mantine/core';
import '@mantine/core/styles.css';
import '@fontsource-variable/inter';
import './styles.css';
import App from './App';
const theme = createTheme({
  primaryColor: 'teal',
  primaryShade: 7,
  fontFamily: 'Inter Variable, Inter, system-ui, sans-serif',
  headings: { fontFamily: 'Inter Variable, Inter, system-ui, sans-serif' },
  defaultRadius: 'xs',
  colors: {
    teal: [
      '#edf8f5',
      '#d5ece5',
      '#afdbcf',
      '#86c8b8',
      '#62b49f',
      '#43a18a',
      '#2b8b75',
      '#1e7462',
      '#175e50',
      '#104b40',
    ],
  },
  components: {
    Button: { defaultProps: { size: 'sm', fw: 550 } },
    Input: { defaultProps: { size: 'md' } },
    Select: { defaultProps: { size: 'md' } },
    Badge: { defaultProps: { fw: 550 } },
  },
});
createRoot(document.getElementById('root')!).render(
  <MantineProvider forceColorScheme="light" theme={theme}>
    <App />
  </MantineProvider>,
);
