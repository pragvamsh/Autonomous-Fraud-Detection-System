import {
    Box, Container, Grid, Typography, Link, Divider,
    IconButton, Stack, TextField, Button,
} from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import FacebookIcon from '@mui/icons-material/Facebook';
import TwitterIcon from '@mui/icons-material/Twitter';
import LinkedInIcon from '@mui/icons-material/LinkedIn';
import InstagramIcon from '@mui/icons-material/Instagram';
import YouTubeIcon from '@mui/icons-material/YouTube';
import PhoneIcon from '@mui/icons-material/Phone';
import EmailIcon from '@mui/icons-material/Email';
import LocationOnIcon from '@mui/icons-material/LocationOn';

const footerSections = [
    {
        title: 'About EagleTrust',
        links: [
            'About Us', 'Leadership Team', 'Investor Relations',
            'Press & Media', 'Careers', 'CSR Initiatives',
        ],
    },
    {
        title: 'Products',
        links: [
            'Savings Account', 'Current Account', 'Fixed Deposit',
            'Personal Loan', 'Home Loan', 'Credit Cards',
        ],
    },
    {
        title: 'Support',
        links: [
            'Help Center', 'Branch Locator', 'ATM Locator',
            'Grievance Redressal', 'RBI Ombudsman', 'Fraud Reporting',
        ],
    },
];

const socialLinks = [
    { icon: <FacebookIcon />, label: 'Facebook', color: '#1877f2' },
    { icon: <TwitterIcon />, label: 'Twitter / X', color: '#1da1f2' },
    { icon: <LinkedInIcon />, label: 'LinkedIn', color: '#0a66c2' },
    { icon: <InstagramIcon />, label: 'Instagram', color: '#e4405f' },
    { icon: <YouTubeIcon />, label: 'YouTube', color: '#ff0000' },
];

export default function Footer() {
    return (
        <Box
            id="footer"
            component="footer"
            sx={{
                background: 'linear-gradient(180deg, #7f5539 0%, #7f5539 100%)',
                color: '#e6ccb2',
                pt: { xs: 8, md: 10 },
                pb: 4,
            }}
        >
            <Container maxWidth="xl">
                <Grid container spacing={5}>
                    {/* Brand column */}
                    <Grid item xs={12} md={3.5}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
                            <Box sx={{
                                width: 44, height: 44,
                                background: 'linear-gradient(135deg, #9c6644, #9c6644)',
                                borderRadius: '10px',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}>
                                <AccountBalanceIcon sx={{ color: '#e6ccb2', fontSize: 26 }} />
                            </Box>
                            <Box>
                                <Typography variant="h6" sx={{ fontWeight: 800, color: '#e6ccb2', lineHeight: 1.1 }}>EagleTrust</Typography>
                                <Typography variant="caption" sx={{ color: '#9c6644', fontWeight: 600, letterSpacing: '0.1em' }}>BANK</Typography>
                            </Box>
                        </Box>
                        <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.55)', lineHeight: 1.8, mb: 3, maxWidth: 280 }}>
                            EagleTrust Bank is a trusted financial institution licensed by the Reserve Bank of India.
                            Serving millions across 29 states with integrity and innovation since 1978.
                        </Typography>
                        {/* Contact */}
                        <Stack spacing={1.5}>
                            {[
                                { icon: <PhoneIcon sx={{ fontSize: 16 }} />, text: '1800-209-4747 (Toll Free)' },
                                { icon: <EmailIcon sx={{ fontSize: 16 }} />, text: 'support@eagletrustbank.in' },
                                { icon: <LocationOnIcon sx={{ fontSize: 16 }} />, text: 'EagleTrust House, BKC, Mumbai - 400051' },
                            ].map((item) => (
                                <Box key={item.text} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                                    <Box sx={{ color: '#9c6644', mt: '2px', flexShrink: 0 }}>{item.icon}</Box>
                                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.82rem', lineHeight: 1.5 }}>
                                        {item.text}
                                    </Typography>
                                </Box>
                            ))}
                        </Stack>
                    </Grid>

                    {/* Link columns */}
                    {footerSections.map((section) => (
                        <Grid item xs={6} md={2} key={section.title}>
                            <Typography
                                variant="body2"
                                sx={{ fontWeight: 700, color: '#ded5cfff', mb: 2.5, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.75rem' }}
                            >
                                {section.title}
                            </Typography>
                            <Stack spacing={1.2}>
                                {section.links.map((link) => (
                                    <Link
                                        key={link}
                                        href="#"
                                        onClick={(e) => e.preventDefault()}
                                        underline="none"
                                        sx={{
                                            color: 'rgba(255,255,255,0.55)',
                                            fontSize: '0.85rem',
                                            transition: 'color 0.2s',
                                            '&:hover': { color: '#e6ccb2' },
                                        }}
                                    >
                                        {link}
                                    </Link>
                                ))}
                            </Stack>
                        </Grid>
                    ))}

                    {/* Newsletter */}
                    <Grid item xs={12} md={2.5}>
                        <Typography
                            variant="body2"
                            sx={{ fontWeight: 700, color: '#ded5cfff', mb: 2.5, letterSpacing: 1, textTransform: 'uppercase', fontSize: '0.75rem' }}
                        >
                            Stay Updated
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.55)', mb: 2, fontSize: '0.85rem', lineHeight: 1.6 }}>
                            Subscribe to get RBI circulars, banking news, and exclusive offers.
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column' }}>
                            <TextField
                                placeholder="your@email.com"
                                size="small"
                                variant="outlined"
                                fullWidth
                                sx={{
                                    '& .MuiOutlinedInput-root': {
                                        color: '#e6ccb2',
                                        background: 'rgba(255,255,255,0.08)',
                                        borderRadius: 2,
                                        '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                                        '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.4)' },
                                        '&.Mui-focused fieldset': { borderColor: '#9c6644' },
                                    },
                                    '& input::placeholder': { color: 'rgba(255,255,255,0.35)', fontSize: '0.85rem' },
                                }}
                            />
                            <Button
                                variant="contained"
                                fullWidth
                                sx={{
                                    background: 'linear-gradient(135deg, #9c6644, #9c6644)',
                                    color: '#7f5539',
                                    fontWeight: 700,
                                    borderRadius: 2,
                                    '&:hover': { background: 'linear-gradient(135deg, #7f5539, #9c6644)' },
                                }}
                            >
                                Subscribe
                            </Button>
                        </Box>
                        {/* Social icons */}
                        <Box sx={{ display: 'flex', gap: 1, mt: 3, flexWrap: 'wrap' }}>
                            {socialLinks.map((social) => (
                                <IconButton
                                    key={social.label}
                                    aria-label={social.label}
                                    size="small"
                                    sx={{
                                        color: 'rgba(255,255,255,0.55)',
                                        border: '1px solid rgba(255,255,255,0.15)',
                                        width: 36, height: 36,
                                        transition: 'all 0.2s ease',
                                        '&:hover': {
                                            color: social.color,
                                            borderColor: social.color,
                                            background: `${social.color}15`,
                                            transform: 'translateY(-2px)',
                                        },
                                    }}
                                >
                                    {social.icon}
                                </IconButton>
                            ))}
                        </Box>
                    </Grid>
                </Grid>

                <Divider sx={{ borderColor: 'rgba(255,255,255,0.1)', my: 5 }} />

                {/* Bottom bar */}
                <Box sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', md: 'row' },
                    justifyContent: 'space-between',
                    alignItems: { xs: 'flex-start', md: 'center' },
                    gap: 2,
                }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.35)', lineHeight: 1.6, maxWidth: { md: 600 } }}>
                        © 2024 EagleTrust Bank Ltd. All rights reserved. EagleTrust Bank is a fictitious entity created for demonstration purposes only.
                        This portal does not constitute an offer for any banking product or service. DICGC insured up to ₹5,00,000.
                        Investments are subject to market risks. Please read all offer documents carefully.
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                        {['Privacy Policy', 'Terms of Use', 'Cookie Policy', 'PMLA Policy'].map((item) => (
                            <Link
                                key={item}
                                href="#"
                                onClick={(e) => e.preventDefault()}
                                underline="hover"
                                sx={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem', '&:hover': { color: '#9c6644' } }}
                            >
                                {item}
                            </Link>
                        ))}
                    </Box>
                </Box>
            </Container>
        </Box>
    );
}
