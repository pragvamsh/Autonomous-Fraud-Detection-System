import { Box, Container, Typography, Grid, Paper } from '@mui/material';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import RequestQuoteIcon from '@mui/icons-material/RequestQuote';
import CreditScoreIcon from '@mui/icons-material/CreditScore';
import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import QrCode2Icon from '@mui/icons-material/QrCode2';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';

const quickLinks = [
    { icon: <CompareArrowsIcon />, label: 'Fund Transfer', color: '#7f5539', bg: '#e3f2fd' },
    { icon: <ReceiptLongIcon />, label: 'Pay Bills', color: '#e65100', bg: '#fff8e1' },
    { icon: <AccountBalanceWalletIcon />, label: 'Check Balance', color: '#b08968', bg: '#e8f5e9' },
    { icon: <RequestQuoteIcon />, label: 'Apply Loan', color: '#7b1fa2', bg: '#f3e5f5' },
    { icon: <CreditScoreIcon />, label: 'Credit Card', color: '#ddb892', bg: '#fce4ec' },
    { icon: <CurrencyExchangeIcon />, label: 'Forex / Travel', color: '#00695c', bg: '#e0f2f1' },
    { icon: <QrCode2Icon />, label: 'UPI / QR Pay', color: '#9c6644', bg: '#fff9e6' },
    { icon: <SupportAgentIcon />, label: 'Customer Care', color: '#1565c0', bg: '#e8eaf6' },
];

export default function QuickLinksSection() {
    return (
        <Box
            id="quicklinks"
            sx={{
                py: { xs: 8, md: 10 },
                background: '#e6ccb2',
            }}
        >
            <Container maxWidth="xl">
                <Box sx={{ textAlign: 'center', mb: { xs: 5, md: 7 } }}>
                    <Typography
                        variant="overline"
                        sx={{ color: '#9c6644', fontWeight: 700, letterSpacing: 3, fontSize: '0.8rem' }}
                    >
                        Quick Access
                    </Typography>
                    <Typography
                        variant="h2"
                        sx={{
                            color: '#7f5539',
                            fontWeight: 800,
                            fontSize: { xs: '1.8rem', md: '2.5rem' },
                            mt: 1, mb: 1.5,
                        }}
                    >
                        Quick Links
                    </Typography>
                    <Typography variant="body1" sx={{ color: '#9c6644', maxWidth: 480, mx: 'auto' }}>
                        Access the most used banking features in one click — fast, secure, and always available.
                    </Typography>
                </Box>

                <Grid container spacing={2.5} justifyContent="center">
                    {quickLinks.map((item) => (
                        <Grid item xs={6} sm={4} md={3} lg={1.5} key={item.label}>
                            <Paper
                                elevation={0}
                                sx={{
                                    p: { xs: 2, md: 2.5 },
                                    borderRadius: 3,
                                    border: '1.5px solid rgba(127, 85, 57,0.06)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: 1.5,
                                    cursor: 'pointer',
                                    transition: 'all 0.25s ease',
                                    '&:hover': {
                                        borderColor: item.color,
                                        boxShadow: `0 8px 30px ${item.color}20`,
                                        transform: 'translateY(-6px)',
                                        '& .quick-icon-box': { background: item.color },
                                        '& .quick-icon': { color: '#e6ccb2' },
                                    },
                                }}
                            >
                                <Box
                                    className="quick-icon-box"
                                    sx={{
                                        width: 56,
                                        height: 56,
                                        borderRadius: 2.5,
                                        background: item.bg,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        transition: 'background 0.25s ease',
                                    }}
                                >
                                    <Box
                                        className="quick-icon"
                                        sx={{
                                            color: item.color,
                                            transition: 'color 0.25s ease',
                                            display: 'flex',
                                            '& .MuiSvgIcon-root': { fontSize: 26 },
                                        }}
                                    >
                                        {item.icon}
                                    </Box>
                                </Box>
                                <Typography
                                    variant="body2"
                                    sx={{
                                        fontWeight: 600,
                                        color: '#7f5539',
                                        textAlign: 'center',
                                        fontSize: '0.8rem',
                                        lineHeight: 1.3,
                                    }}
                                >
                                    {item.label}
                                </Typography>
                            </Paper>
                        </Grid>
                    ))}
                </Grid>

                {/* Trust indicators bar */}
                <Box
                    sx={{
                        mt: { xs: 6, md: 8 },
                        p: { xs: 3, md: 4 },
                        borderRadius: 3,
                        background: 'linear-gradient(135deg, #f8f9ff 0%, #e8edf8 100%)',
                        border: '1px solid rgba(127, 85, 57,0.1)',
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 3,
                        justifyContent: 'space-around',
                        alignItems: 'center',
                    }}
                >
                    {[
                        { value: '256-bit', label: 'SSL Encryption' },
                        { value: 'RBI', label: 'Licensed & Regulated' },
                        { value: '₹5 Lakh', label: 'DICGC Insured' },
                        { value: '24/7', label: 'Customer Support' },
                        { value: 'ISO 27001', label: 'Security Certified' },
                    ].map((item) => (
                        <Box key={item.label} sx={{ textAlign: 'center' }}>
                            <Typography variant="h6" sx={{ color: '#7f5539', fontWeight: 800 }}>
                                {item.value}
                            </Typography>
                            <Typography variant="caption" sx={{ color: '#9c6644', fontWeight: 500 }}>
                                {item.label}
                            </Typography>
                        </Box>
                    ))}
                </Box>
            </Container>
        </Box>
    );
}
