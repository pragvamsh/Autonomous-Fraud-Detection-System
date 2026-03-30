import { useState, useEffect } from 'react';
import {
    AppBar, Toolbar, Box, Button, IconButton, Drawer, List,
    ListItem, ListItemButton, ListItemText, useScrollTrigger,
    Slide, Typography, useMediaQuery, useTheme, Container,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CloseIcon from '@mui/icons-material/Close';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import { useNavigate, Link } from 'react-router-dom';

const navLinks = [
    { label: 'Home', href: '#home' },
    { label: 'Services', href: '#services' },
    { label: 'Quick Links', href: '#quicklinks' },
    { label: 'Videos', href: '#videos' },
    { label: 'Contact', href: '#footer' },
];

function HideOnScroll({ children }) {
    const trigger = useScrollTrigger();
    return <Slide appear={false} direction="down" in={!trigger}>{children}</Slide>;
}

export default function Navbar() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [scrolled, setScrolled] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 60);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleNavClick = (href) => {
        setDrawerOpen(false);
        if (href.startsWith('#')) {
            const el = document.querySelector(href);
            if (el) el.scrollIntoView({ behavior: 'smooth' });
        }
    };

    return (
        <>
            <HideOnScroll>
                <AppBar
                    position="fixed"
                    elevation={scrolled ? 4 : 0}
                    sx={{
                        background: scrolled
                            ? 'rgba(127, 85, 57, 0.97)'
                            : 'linear-gradient(135deg, #7f5539 0%, #7f5539 100%)',
                        backdropFilter: 'blur(10px)',
                        transition: 'all 0.3s ease',
                        borderBottom: scrolled ? 'none' : '1px solid rgba(255,255,255,0.1)',
                    }}
                >
                    <Container maxWidth="xl">
                        <Toolbar disableGutters sx={{ py: 0.5 }}>
                            {/* Logo */}
                            <Box
                                component={Link}
                                to="/"
                                sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 1.5,
                                    textDecoration: 'none',
                                    flexGrow: { xs: 1, md: 0 },
                                }}
                            >
                                <Box
                                    sx={{
                                        width: 40,
                                        height: 40,
                                        background: 'linear-gradient(135deg, #9c6644, #9c6644)',
                                        borderRadius: '10px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        boxShadow: '0 4px 12px rgba(156, 102, 68,0.4)',
                                    }}
                                >
                                    <AccountBalanceIcon sx={{ color: '#e6ccb2', fontSize: 24 }} />
                                </Box>
                                <Box>
                                    <Typography
                                        variant="h6"
                                        sx={{
                                            color: '#e6ccb2',
                                            fontWeight: 800,
                                            letterSpacing: '-0.3px',
                                            lineHeight: 1.1,
                                            fontSize: { xs: '1rem', sm: '1.15rem' },
                                        }}
                                    >
                                        EagleTrust
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        sx={{ color: '#e6ccb2', fontWeight: 500, letterSpacing: '0.05em' }}
                                    >
                                        BANK
                                    </Typography>
                                </Box>
                            </Box>

                            {/* Desktop nav links */}
                            {!isMobile && (
                                <Box sx={{ display: 'flex', alignItems: 'center', mx: 'auto', gap: 0.5 }}>
                                    {navLinks.map((link) => (
                                        <Button
                                            key={link.label}
                                            onClick={() => handleNavClick(link.href)}
                                            sx={{
                                                color: 'rgba(255,255,255,0.85)',
                                                fontWeight: 500,
                                                fontSize: '0.9rem',
                                                px: 2,
                                                '&:hover': {
                                                    color: '#9c6644',
                                                    background: 'rgba(255,255,255,0.08)',
                                                },
                                            }}
                                        >
                                            {link.label}
                                        </Button>
                                    ))}
                                </Box>
                            )}

                            {/* CTA Buttons */}
                            {!isMobile && (
                                <Box sx={{ display: 'flex', gap: 1.5 }}>
                                    <Button
                                        variant="outlined"
                                        id="nav-register-btn"
                                        onClick={() => navigate('/register')}
                                        sx={{
                                            background: 'linear-gradient(135deg, #e4ac87ff, #e6ded9ff)',
                                            color: '#7f5539',
                                            fontWeight: 700,
                                            '&:hover': {
                                                background: 'linear-gradient(135deg, #d5d0cdff, #e4ac87ff)',
                                            },
                                        }}
                                    >
                                        Register as Customer
                                    </Button>
                                    <Button
                                        variant="contained"
                                        id="nav-login-btn"
                                        onClick={() => navigate('/login')}
                                        sx={{
                                            background: 'linear-gradient(135deg, #e4ac87ff, #e6ded9ff)',
                                            color: '#7f5539',
                                            fontWeight: 700,
                                            '&:hover': {
                                                background: 'linear-gradient(135deg, #d5d0cdff, #e4ac87ff)',
                                            },
                                        }}
                                    >
                                        Login
                                    </Button>
                                </Box>
                            )}

                            {/* Mobile hamburger */}
                            {isMobile && (
                                <IconButton
                                    edge="end"
                                    onClick={() => setDrawerOpen(true)}
                                    sx={{ color: '#e6ccb2' }}
                                    aria-label="Open navigation menu"
                                >
                                    <MenuIcon />
                                </IconButton>
                            )}
                        </Toolbar>
                    </Container>
                </AppBar>
            </HideOnScroll>

            {/* Mobile Drawer */}
            <Drawer
                anchor="right"
                open={drawerOpen}
                onClose={() => setDrawerOpen(false)}
                PaperProps={{
                    sx: {
                        width: 280,
                        background: 'linear-gradient(160deg, #7f5539 0%, #7f5539 100%)',
                        color: '#e6ccb2',
                    },
                }}
            >
                <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6" sx={{ fontWeight: 700, color: '#9c6644' }}>
                        EagleTrust Bank
                    </Typography>
                    <IconButton onClick={() => setDrawerOpen(false)} sx={{ color: '#e6ccb2' }}>
                        <CloseIcon />
                    </IconButton>
                </Box>
                <List>
                    {navLinks.map((link) => (
                        <ListItem key={link.label} disablePadding>
                            <ListItemButton
                                onClick={() => handleNavClick(link.href)}
                                sx={{ '&:hover': { background: 'rgba(255,255,255,0.1)' } }}
                            >
                                <ListItemText
                                    primary={link.label}
                                    primaryTypographyProps={{ fontWeight: 500, color: '#e6ccb2' }}
                                />
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>
                <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5, mt: 2 }}>
                    <Button
                        fullWidth
                        variant="outlined"
                        id="mobile-register-btn"
                        onClick={() => { setDrawerOpen(false); navigate('/register'); }}
                        sx={{ color: '#9c6644', borderColor: '#9c6644', fontWeight: 600 }}
                    >
                        Register as Customer
                    </Button>
                    <Button
                        fullWidth
                        variant="contained"
                        id="mobile-login-btn"
                        onClick={() => { setDrawerOpen(false); navigate('/login'); }}
                        sx={{ background: 'linear-gradient(135deg, #9c6644, #9c6644)', color: '#7f5539', fontWeight: 700 }}
                    >
                        Login
                    </Button>
                </Box>
            </Drawer>
        </>
    );
}
