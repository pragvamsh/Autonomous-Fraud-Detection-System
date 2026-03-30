import {
    Box, Container, Typography, Grid, Card, CardContent,
    Button, Chip,
} from '@mui/material';
import SavingsIcon from '@mui/icons-material/Savings';
import CreditCardIcon from '@mui/icons-material/CreditCard';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import LaptopIcon from '@mui/icons-material/Laptop';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ShieldIcon from '@mui/icons-material/Shield';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

const services = [
    {
        icon: <SavingsIcon sx={{ fontSize: 48 }} />,
        title: 'Savings Account',
        description: 'Earn up to 7% interest p.a. with zero minimum balance on our premium savings account.',
        tag: 'Most Popular',
        tagColor: '#b08968',
        color: '#e3f2fd',
        iconColor: '#7f5539',
    },
    {
        icon: <AccountBalanceIcon sx={{ fontSize: 48 }} />,
        title: 'Personal Loans',
        description: 'Instant loan approval in 30 minutes. Get up to ₹50 Lakhs at competitive interest rates.',
        tag: 'Low Rates',
        tagColor: '#e65100',
        color: '#fff8e1',
        iconColor: '#9c6644',
    },
    {
        icon: <CreditCardIcon sx={{ fontSize: 48 }} />,
        title: 'Credit Cards',
        description: '5X reward points on shopping. Lifetime free cards with travel benefits & cashback.',
        tag: 'Exclusive Offers',
        tagColor: '#7b1fa2',
        color: '#f3e5f5',
        iconColor: '#7b1fa2',
    },
    {
        icon: <LaptopIcon sx={{ fontSize: 48 }} />,
        title: 'Net Banking',
        description: 'Secure 24/7 online banking. Transfer funds, pay bills, invest — all from your home.',
        tag: '256-bit SSL',
        tagColor: '#1565c0',
        color: '#e8f5e9',
        iconColor: '#1565c0',
    },
    {
        icon: <TrendingUpIcon sx={{ fontSize: 48 }} />,
        title: 'Investments & MF',
        description: 'Grow your wealth with SIPs, Fixed Deposits, and curated Mutual Fund portfolios.',
        tag: 'High Returns',
        tagColor: '#b08968',
        color: '#e3f2fd',
        iconColor: '#b08968',
    },
    {
        icon: <ShieldIcon sx={{ fontSize: 48 }} />,
        title: 'Insurance',
        description: 'Comprehensive life, health, and vehicle insurance at the best premiums across India.',
        tag: 'IRDAI Approved',
        tagColor: '#7f5539',
        color: '#fce4ec',
        iconColor: '#ddb892',
    },
];

export default function ServicesSection() {
    return (
        <Box
            id="services"
            sx={{
                py: { xs: 8, md: 12 },
                background: '#ede0d4',
            }}
        >
            <Container maxWidth="xl">
                {/* Section header */}
                <Box sx={{ textAlign: 'center', mb: { xs: 6, md: 8 } }}>
                    <Typography
                        variant="overline"
                        sx={{ color: '#9c6644', fontWeight: 700, letterSpacing: 3, fontSize: '0.8rem' }}
                    >
                        What We Offer
                    </Typography>
                    <Typography
                        variant="h2"
                        sx={{
                            color: '#7f5539',
                            fontWeight: 800,
                            fontSize: { xs: '1.8rem', md: '2.5rem' },
                            mb: 2,
                            mt: 1,
                        }}
                    >
                        Our Products &{' '}
                        <Box component="span" sx={{ color: '#7f5539' }}>Services</Box>
                    </Typography>
                    <Typography
                        variant="body1"
                        sx={{ color: '#9c6644', maxWidth: 560, mx: 'auto', lineHeight: 1.7 }}
                    >
                        Designed for every stage of your life — from your first savings account
                        to wealth management for the future.
                    </Typography>
                </Box>

                <Grid container spacing={3}>
                    {services.map((service) => (
                        <Grid item xs={12} sm={6} md={4} key={service.title}>
                            <Card
                                sx={{
                                    height: '100%',
                                    border: '1px solid rgba(127, 85, 57,0.06)',
                                    cursor: 'pointer',
                                    position: 'relative',
                                    overflow: 'visible',
                                }}
                            >
                                <CardContent sx={{ p: 3.5 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                        <Box
                                            sx={{
                                                width: 72,
                                                height: 72,
                                                borderRadius: 3,
                                                background: service.color,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                color: service.iconColor,
                                            }}
                                        >
                                            {service.icon}
                                        </Box>
                                        <Chip
                                            label={service.tag}
                                            size="small"
                                            sx={{
                                                background: `${service.tagColor}18`,
                                                color: service.tagColor,
                                                fontWeight: 600,
                                                fontSize: '0.7rem',
                                                border: `1px solid ${service.tagColor}40`,
                                            }}
                                        />
                                    </Box>
                                    <Typography variant="h5" sx={{ fontWeight: 700, color: '#7f5539', mb: 1.5 }}>
                                        {service.title}
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: '#9c6644', lineHeight: 1.7, mb: 2.5 }}>
                                        {service.description}
                                    </Typography>
                                    <Button
                                        endIcon={<ArrowForwardIcon />}
                                        sx={{
                                            color: '#7f5539',
                                            fontWeight: 600,
                                            p: 0,
                                            '&:hover': {
                                                background: 'transparent',
                                                color: '#9c6644',
                                                '& .MuiButton-endIcon': { transform: 'translateX(4px)' },
                                            },
                                            '& .MuiButton-endIcon': { transition: 'transform 0.2s' },
                                        }}
                                    >
                                        Learn More
                                    </Button>
                                </CardContent>
                            </Card>
                        </Grid>
                    ))}
                </Grid>
            </Container>
        </Box>
    );
}
