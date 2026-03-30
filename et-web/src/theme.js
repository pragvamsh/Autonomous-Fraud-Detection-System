import { createTheme } from '@mui/material/styles';

const theme = createTheme({
    palette: {
        primary: {
            main: '#7f5539',
            light: '#9c6644',
            dark: '#7f5539',
            contrastText: '#e6ccb2',
        },
        secondary: {
            main: '#9c6644',
            light: '#9c6644',
            dark: '#7f5539',
            contrastText: '#e6ccb2',
        },
        background: {
            default: '#ede0d4',
            paper: '#e6ccb2',
        },
        text: {
            primary: '#7f5539',
            secondary: '#9c6644',
        },
        success: { main: '#b08968' },
        error: { main: '#ddb892' },
    },
    typography: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        h1: { fontWeight: 800 },
        h2: { fontWeight: 700 },
        h3: { fontWeight: 700 },
        h4: { fontWeight: 600 },
        h5: { fontWeight: 600 },
        h6: { fontWeight: 600 },
        button: { textTransform: 'none', fontWeight: 600 },
    },
    shape: { borderRadius: 12 },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    borderRadius: 8,
                    padding: '10px 24px',
                    fontSize: '0.95rem',
                    boxShadow: 'none',
                    '&:hover': { boxShadow: '0 4px 16px rgba(127, 85, 57,0.25)' },
                },
                containedPrimary: {
                    background: 'linear-gradient(135deg, #7f5539 0%, #9c6644 100%)',
                },
                containedSecondary: {
                    background: 'linear-gradient(135deg, #9c6644 0%, #9c6644 100%)',
                    color: '#e6ccb2',
                },
            },
        },
        MuiCard: {
            styleOverrides: {
                root: {
                    borderRadius: 16,
                    boxShadow: '0 2px 20px rgba(127, 85, 57,0.08)',
                    transition: 'transform 0.25s ease, box-shadow 0.25s ease',
                    '&:hover': {
                        transform: 'translateY(-6px)',
                        boxShadow: '0 12px 40px rgba(127, 85, 57,0.15)',
                    },
                },
            },
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    boxShadow: '0 2px 20px rgba(127, 85, 57,0.1)',
                },
            },
        },
    },
});

export default theme;
