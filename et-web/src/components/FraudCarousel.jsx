import Slider from 'react-slick';
import { Box, Container, Typography, Card, CardContent, Chip } from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PhishingIcon from '@mui/icons-material/Phishing';
import SmartphoneIcon from '@mui/icons-material/Smartphone';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import SecurityIcon from '@mui/icons-material/Security';

const fraudSlides = [
    {
        icon: <PhishingIcon sx={{ fontSize: 60 }} />,
        title: 'Beware of Phishing Emails',
        subtitle: 'RBI Advisory',
        tip: 'RBI or any bank will NEVER ask for your OTP, PIN, CVV, or password via email, SMS, or phone call. Always verify before sharing any information.',
        bg: 'linear-gradient(135deg, #b71c1c 0%, #e53935 100%)',
        accentColor: '#ffcdd2',
    },
    {
        icon: <SmartphoneIcon sx={{ fontSize: 60 }} />,
        title: 'SIM Swap Fraud Alert',
        subtitle: 'Cybercrime Division',
        tip: 'Fraudsters may port your SIM to intercept OTPs. If your mobile network disappears suddenly, contact your telecom provider immediately and inform your bank.',
        bg: 'linear-gradient(135deg, #e65100 0%, #ff6d00 100%)',
        accentColor: '#ffe0b2',
    },
    {
        icon: <LinkOffIcon sx={{ fontSize: 60 }} />,
        title: 'Fake Banking Websites',
        subtitle: 'RBI Guideline',
        tip: 'Always check the URL before logging in. Secure banking URLs start with https:// and display a padlock icon. Bookmark our official site to avoid fake lookalike pages.',
        bg: 'linear-gradient(135deg, #1a237e 0%, #283593 100%)',
        accentColor: '#c5cae9',
    },
    {
        icon: <AccountBalanceWalletIcon sx={{ fontSize: 60 }} />,
        title: 'UPI Fraud & Fake Requests',
        subtitle: 'NPCI Warning',
        tip: 'Collecting money via UPI does NOT require your PIN. Never enter your UPI PIN for "Receive Money" requests. Pin is only for sending money.',
        bg: 'linear-gradient(135deg, #006064 0%, #00838f 100%)',
        accentColor: '#b2ebf2',
    },
    {
        icon: <SecurityIcon sx={{ fontSize: 60 }} />,
        title: 'KYC Fraud via Calls',
        subtitle: 'RBI Public Advisory',
        tip: 'Fake agents posing as bank officials request remote access or KYC updates via apps. RBI mandates KYC updates only through official bank branches or verified digital channels.',
        bg: 'linear-gradient(135deg, #4a148c 0%, #7b1fa2 100%)',
        accentColor: '#e1bee7',
    },
];

const settings = {
    dots: true,
    infinite: true,
    speed: 600,
    slidesToShow: 1,
    slidesToScroll: 1,
    autoplay: true,
    autoplaySpeed: 4500,
    pauseOnHover: true,
    arrows: true,
};

export default function FraudCarousel() {
    return (
        <Box
            id="fraud-awareness"
            sx={{
                py: { xs: 8, md: 10 },
                background: 'linear-gradient(180deg, #7f5539 0%, #16213e 100%)',
                position: 'relative',
                overflow: 'hidden',
            }}
        >
            {/* Background pattern */}
            <Box sx={{
                position: 'absolute', inset: 0,
                backgroundImage: `radial-gradient(circle at 20% 50%, rgba(156, 102, 68,0.05) 0%, transparent 50%),
                          radial-gradient(circle at 80% 50%, rgba(127, 85, 57,0.1) 0%, transparent 50%)`,
                pointerEvents: 'none',
            }} />

            <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
                <Box sx={{ textAlign: 'center', mb: 6 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                        <Box sx={{
                            display: 'flex', alignItems: 'center', gap: 1,
                            background: 'rgba(156, 102, 68,0.15)',
                            border: '1px solid rgba(156, 102, 68,0.3)',
                            borderRadius: 20,
                            px: 2, py: 0.5,
                        }}>
                            <WarningAmberIcon sx={{ color: '#e4dedbff', fontSize: 18 }} />
                            <Typography variant="overline" sx={{ color: '#e4dedbff', fontWeight: 700, letterSpacing: 2, fontSize: '0.75rem' }}>
                                RBI Fraud Awareness
                            </Typography>
                        </Box>
                    </Box>
                    <Typography variant="h2" sx={{
                        color: '#e6ccb2', fontWeight: 800,
                        fontSize: { xs: '1.7rem', md: '2.4rem' }, mb: 1,
                    }}>
                        Stay Safe from Financial Fraud
                    </Typography>
                    <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.55)', maxWidth: 520, mx: 'auto' }}>
                        Important advisories from the Reserve Bank of India to protect your money and digital identity.
                    </Typography>
                </Box>

                <Box sx={{ maxWidth: 800, mx: 'auto', '& .slick-dots li button:before': { color: '#9c6644' } }}>
                    <Slider {...settings}>
                        {fraudSlides.map((slide) => (
                            <Box key={slide.title} sx={{ px: 1, pb: 5 }}>
                                <Card
                                    sx={{
                                        background: slide.bg,
                                        borderRadius: 4,
                                        border: 'none',
                                        boxShadow: '0 20px 60px rgba(127, 85, 57,0.4)',
                                        overflow: 'hidden',
                                        position: 'relative',
                                        '&:hover': { transform: 'none' },
                                    }}
                                >
                                    {/* Decorative circle */}
                                    <Box sx={{
                                        position: 'absolute', top: -40, right: -40,
                                        width: 200, height: 200, borderRadius: '50%',
                                        background: 'rgba(255,255,255,0.06)',
                                    }} />
                                    <CardContent sx={{ p: { xs: 3.5, md: 5 }, position: 'relative', zIndex: 1 }}>
                                        <Chip
                                            label={slide.subtitle}
                                            size="small"
                                            sx={{
                                                mb: 3,
                                                background: 'rgba(255,255,255,0.15)',
                                                color: '#e6ccb2',
                                                fontWeight: 600,
                                                backdropFilter: 'blur(10px)',
                                                border: '1px solid rgba(255,255,255,0.2)',
                                            }}
                                        />
                                        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: { sm: 'center' }, gap: 3 }}>
                                            <Box
                                                sx={{
                                                    width: 90, height: 90,
                                                    borderRadius: 3,
                                                    flexShrink: 0,
                                                    background: 'rgba(255,255,255,0.12)',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    color: slide.accentColor,
                                                }}
                                            >
                                                {slide.icon}
                                            </Box>
                                            <Box>
                                                <Typography variant="h4" sx={{
                                                    color: '#e6ccb2', fontWeight: 800, mb: 1.5,
                                                    fontSize: { xs: '1.3rem', md: '1.6rem' },
                                                }}>
                                                    {slide.title}
                                                </Typography>
                                                <Typography variant="body1" sx={{
                                                    color: slide.accentColor, lineHeight: 1.8,
                                                    fontSize: { xs: '0.9rem', md: '1rem' },
                                                }}>
                                                    {slide.tip}
                                                </Typography>
                                            </Box>
                                        </Box>
                                    </CardContent>
                                </Card>
                            </Box>
                        ))}
                    </Slider>
                </Box>
            </Container>
        </Box>
    );
}
