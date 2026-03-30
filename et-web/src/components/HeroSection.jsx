import { Box, Typography, Button, Container, Stack, Chip } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import { useNavigate } from 'react-router-dom';

export default function HeroSection() {
    const navigate = useNavigate();

    const handleServicesClick = () => {
        const el = document.querySelector('#services');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
    };

    return (
        <Box
            id="home"
            sx={{
                position: 'relative',
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                overflow: 'hidden',
                background: 'linear-gradient(-45deg, #7f5539, #7f5539, #9c6644, #7f5539)',
                backgroundSize: '400% 400%',
                animation: 'gradientShift 12s ease infinite',
            }}
        >
            {/* Decorative circles */}
            <Box sx={{
                position: 'absolute', top: '-10%', right: '-5%',
                width: { xs: 300, md: 600 }, height: { xs: 300, md: 600 },
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(156, 102, 68,0.15) 0%, transparent 70%)',
                pointerEvents: 'none',
            }} />
            <Box sx={{
                position: 'absolute', bottom: '-15%', left: '-8%',
                width: { xs: 250, md: 500 }, height: { xs: 250, md: 500 },
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(26,77,181,0.3) 0%, transparent 70%)',
                pointerEvents: 'none',
            }} />
            {/* Grid pattern overlay */}
            <Box sx={{
                position: 'absolute', inset: 0,
                backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                pointerEvents: 'none',
            }} />

            <Container maxWidth="xl" sx={{ position: 'relative', zIndex: 2 }}>
                <Box sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', md: 'row' },
                    alignItems: 'center',
                    gap: { xs: 6, md: 4 },
                    py: { xs: 14, md: 8 },
                }}>
                    {/* Left content */}
                    <Box sx={{ flex: 1, maxWidth: { md: '55%' } }}>
                        <Chip
                            label="🏆 India's Most Trusted Bank 2024"
                            className="hero-animate"
                            sx={{
                                mb: 3,
                                background: 'rgba(156, 102, 68,0.2)',
                                color: '#e6ccb2',
                                fontWeight: 600,
                                border: '1px solid rgba(156, 102, 68,0.4)',
                                backdropFilter: 'blur(10px)',
                            }}
                        />
                        <Typography
                            variant="h1"
                            className="hero-animate"
                            sx={{
                                fontSize: { xs: '2.4rem', sm: '3rem', md: '3.6rem', lg: '4rem' },
                                fontWeight: 800,
                                color: '#e6ccb2',
                                lineHeight: 1.15,
                                letterSpacing: '-1px',
                                mb: 2,
                            }}
                        >
                            Banking Made{' '}
                            <Box component="span" sx={{
                                background: 'linear-gradient(135deg, #e2e8e5ff, #e2ae8bff, #e2e8e5ff)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                            }}>
                                Simple.
                            </Box>
                            <br />
                            Future Made{' '}
                            <Box component="span" sx={{
                                background: 'linear-gradient(135deg, #e2e8e5ff, #e2ae8bff, #e2e8e5ff)',
                                backgroundClip: 'text',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                            }}>
                                Bright.
                            </Box>
                        </Typography>
                        <Typography
                            variant="h5"
                            className="hero-animate-delay"
                            sx={{
                                color: 'rgba(255,255,255,0.75)',
                                fontWeight: 400,
                                lineHeight: 1.6,
                                mb: 5,
                                maxWidth: 520,
                                fontSize: { xs: '1rem', md: '1.15rem' },
                            }}
                        >
                            Experience seamless digital banking with industry-leading security,
                            zero hidden fees, and personalized financial solutions built for every Indian.
                        </Typography>
                        <Stack
                            className="hero-animate-delay2"
                            direction={{ xs: 'column', sm: 'row' }}
                            spacing={2}
                        >
                            <Button
                                variant="contained"
                                size="large"
                                id="hero-open-account-btn"
                                endIcon={<ArrowForwardIcon />}
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
                                Open Free Account
                            </Button>
                            <Button
                                variant="outlined"
                                size="large"
                                id="hero-explore-btn"
                                startIcon={<PlayCircleOutlineIcon />}
                                onClick={handleServicesClick}
                                sx={{
                                    color: '#e6ccb2',
                                    borderColor: 'rgba(255,255,255,0.4)',
                                    fontWeight: 600,
                                    fontSize: '1rem',
                                    py: 1.5,
                                    px: 4,
                                    backdropFilter: 'blur(10px)',
                                    '&:hover': {
                                        borderColor: '#e6ccb2',
                                        background: 'rgba(255,255,255,0.1)',
                                    },
                                }}
                            >
                                Explore Services
                            </Button>
                        </Stack>

                        {/* Stats row */}
                        <Box
                            className="hero-animate-delay2"
                            sx={{
                                display: 'flex',
                                gap: { xs: 3, sm: 5 },
                                mt: 6,
                                flexWrap: 'wrap',
                            }}
                        >
                            {[
                                { value: '5Cr+', label: 'Happy Customers' },
                                { value: '₹2L Cr+', label: 'Assets Managed' },
                                { value: '99.9%', label: 'Uptime' },
                            ].map((stat) => (
                                <Box key={stat.label}>
                                    <Typography variant="h4" sx={{ color: '#9c6644', fontWeight: 800 }}>
                                        {stat.value}
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)', fontWeight: 500 }}>
                                        {stat.label}
                                    </Typography>
                                </Box>
                            ))}
                        </Box>
                    </Box>

                    {/* Right — floating card visual */}
                    <Box sx={{
                        flex: 1,
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        position: 'relative',
                    }}>
                        {/* Mock bank card */}
                        <Box sx={{
                            width: { xs: 300, md: 380 },
                            height: { xs: 180, md: 220 },
                            borderRadius: 4,
                            background: 'linear-gradient(135deg, #7f5539 0%, #7f5539 50%, #9c6644 100%)',
                            boxShadow: '0 30px 80px rgba(127, 85, 57,0.5)',
                            position: 'relative',
                            transform: 'perspective(800px) rotateY(-10deg) rotateX(5deg)',
                            transition: 'transform 0.4s ease',
                            overflow: 'hidden',
                            '&:hover': { transform: 'perspective(800px) rotateY(-5deg) rotateX(2deg)' },
                        }}>
                            <Box sx={{
                                position: 'absolute', top: -30, right: -30,
                                width: 140, height: 140, borderRadius: '50%',
                                background: 'rgba(255,255,255,0.08)',
                            }} />
                            <Box sx={{
                                position: 'absolute', bottom: -20, left: -20,
                                width: 100, height: 100, borderRadius: '50%',
                                background: 'rgba(156, 102, 68,0.15)',
                            }} />
                            <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <Box sx={{
                                        width: 44, height: 34, borderRadius: 1,
                                        background: 'linear-gradient(135deg, #9c6644, #ffd700)',
                                    }} />
                                    <Typography sx={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.75rem', fontWeight: 600 }}>
                                        EagleTrust Bank
                                    </Typography>
                                </Box>
                                <Typography sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '1.1rem', fontFamily: 'monospace', letterSpacing: 3 }}>
                                    •••• •••• •••• 4217
                                </Typography>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                                    <Box>
                                        <Typography sx={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.6rem', mb: 0.3 }}>CARD HOLDER</Typography>
                                        <Typography sx={{ color: '#e6ccb2', fontWeight: 600, fontSize: '0.9rem' }}>ADITYA KUMAR</Typography>
                                    </Box>
                                    <Box>
                                        <Typography sx={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.6rem', mb: 0.3 }}>EXPIRES</Typography>
                                        <Typography sx={{ color: '#e6ccb2', fontWeight: 600, fontSize: '0.9rem' }}>12/29</Typography>
                                    </Box>
                                    <Box sx={{
                                        display: 'flex',
                                        '& > *:last-child': { ml: -1.5 },
                                    }}>
                                        <Box sx={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(235,0,27,0.7)' }} />
                                        <Box sx={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(255,163,0,0.7)' }} />
                                    </Box>
                                </Box>
                            </Box>
                        </Box>

                        {/* Floating notification badges */}
                        <Box sx={{
                            position: 'absolute', top: { xs: -10, md: 20 }, right: { xs: 10, md: -20 },
                            background: '#e6ccb2',
                            borderRadius: 3,
                            p: 1.5,
                            boxShadow: '0 10px 40px rgba(127, 85, 57,0.15)',
                            display: 'flex', alignItems: 'center', gap: 1,
                            animation: 'pulse 3s ease-in-out infinite',
                        }}>
                            <Box sx={{ width: 36, height: 36, borderRadius: 2, background: '#e8f5e9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Typography sx={{ fontSize: '1.2rem' }}>✅</Typography>
                            </Box>
                            <Box>
                                <Typography sx={{ fontSize: '0.7rem', color: '#9c6644', fontWeight: 500 }}>Transfer Successful</Typography>
                                <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: '#b08968' }}>₹25,000.00</Typography>
                            </Box>
                        </Box>
                    </Box>
                </Box>
            </Container>

            {/* Bottom wave */}
            <Box sx={{ position: 'absolute', bottom: 0, left: 0, right: 0, lineHeight: 0 }}>
                <svg viewBox="0 0 1440 80" preserveAspectRatio="none" style={{ display: 'block', width: '100%', height: 80 }}>
                    <path d="M0,40 C360,80 1080,0 1440,40 L1440,80 L0,80 Z" fill="#ede0d4" />
                </svg>
            </Box>
        </Box>
    );
}
