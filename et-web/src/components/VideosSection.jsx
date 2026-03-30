import { Box, Container, Typography, Grid, Chip } from '@mui/material';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';

const videos = [
    {
        id: 'v6X92s30BeA',
        title: 'RBI Financial Literacy Initiative',
        description: 'Learn about RBI programs to educate citizens on smart money management, digital banking, and financial security.',
        tag: 'RBI Official',
        tagColor: '#7f5539',
    },
    {
        id: 'mWZvOwIkMHQ',
        title: 'How to Stay Safe from UPI Fraud',
        description: 'A comprehensive guide on identifying and avoiding UPI payment frauds, phishing attacks, and social engineering scams.',
        tag: 'Cyber Safety',
        tagColor: '#ddb892',
    },
    {
        id: 'dWjpucEaC94',
        title: 'Understanding Mutual Funds for Beginners',
        description: 'Everything you need to know about starting your investment journey with SIPs and mutual funds in India.',
        tag: 'Investing 101',
        tagColor: '#b08968',
    },
];

export default function VideosSection() {
    return (
        <Box
            id="videos"
            sx={{
                py: { xs: 8, md: 12 },
                background: '#ede0d4',
            }}
        >
            <Container maxWidth="xl">
                {/* Header */}
                <Box sx={{ textAlign: 'center', mb: { xs: 5, md: 7 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                        <Box sx={{
                            display: 'flex', alignItems: 'center', gap: 1,
                            background: 'rgba(127, 85, 57,0.08)',
                            border: '1px solid rgba(127, 85, 57,0.15)',
                            borderRadius: 20,
                            px: 2, py: 0.5,
                        }}>
                            <PlayCircleIcon sx={{ color: '#7f5539', fontSize: 18 }} />
                            <Typography variant="overline" sx={{ color: '#7f5539', fontWeight: 700, letterSpacing: 2, fontSize: '0.75rem' }}>
                                Video Resources
                            </Typography>
                        </Box>
                    </Box>
                    <Typography
                        variant="h2"
                        sx={{
                            color: '#7f5539',
                            fontWeight: 800,
                            fontSize: { xs: '1.8rem', md: '2.5rem' },
                            mb: 1.5,
                        }}
                    >
                        Financial Literacy &{' '}
                        <Box component="span" sx={{ color: '#7f5539' }}>Education</Box>
                    </Typography>
                    <Typography variant="body1" sx={{ color: '#9c6644', maxWidth: 520, mx: 'auto', lineHeight: 1.7 }}>
                        Watch curated videos on banking, investing, fraud prevention, and smart financial planning.
                    </Typography>
                </Box>

                <Grid container spacing={3}>
                    {videos.map((video) => (
                        <Grid item xs={12} md={4} key={video.id}>
                            <Box
                                sx={{
                                    borderRadius: 4,
                                    overflow: 'hidden',
                                    background: '#e6ccb2',
                                    boxShadow: '0 4px 24px rgba(127, 85, 57,0.08)',
                                    transition: 'all 0.3s ease',
                                    '&:hover': {
                                        transform: 'translateY(-6px)',
                                        boxShadow: '0 16px 48px rgba(127, 85, 57,0.15)',
                                    },
                                }}
                            >
                                {/* Video embed */}
                                <Box className="video-responsive">
                                    <iframe
                                        src={`https://www.youtube.com/embed/${video.id}?rel=0&modestbranding=1`}
                                        title={video.title}
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowFullScreen
                                    />
                                </Box>
                                {/* Info */}
                                <Box sx={{ p: 2.5 }}>
                                    <Chip
                                        label={video.tag}
                                        size="small"
                                        sx={{
                                            mb: 1.5,
                                            background: `${video.tagColor}14`,
                                            color: video.tagColor,
                                            fontWeight: 600,
                                            fontSize: '0.7rem',
                                            border: `1px solid ${video.tagColor}30`,
                                        }}
                                    />
                                    <Typography variant="h6" sx={{ fontWeight: 700, color: '#7f5539', mb: 0.8, lineHeight: 1.3 }}>
                                        {video.title}
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: '#9c6644', lineHeight: 1.6 }}>
                                        {video.description}
                                    </Typography>
                                </Box>
                            </Box>
                        </Grid>
                    ))}
                </Grid>
            </Container>
        </Box>
    );
}
