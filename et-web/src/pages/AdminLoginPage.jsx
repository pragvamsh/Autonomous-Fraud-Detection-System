import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container,
    Paper,
    TextField,
    Button,
    Typography,
    Box,
    Alert,
    CircularProgress
} from '@mui/material';
import { Lock as LockIcon } from '@mui/icons-material';
import axios from 'axios';

const AdminLoginPage = () => {
    const navigate = useNavigate();
    const [credentials, setCredentials] = useState({
        username: '',
        password: ''
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleChange = (e) => {
        setCredentials({
            ...credentials,
            [e.target.name]: e.target.value
        });
        setError('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const response = await axios.post(
                'http://localhost:5000/api/admin/login',
                credentials,
                { withCredentials: true }
            );

            if (response.data.success) {
                navigate('/admin/dashboard');
            } else {
                setError(response.data.error || 'Login failed');
            }
        } catch (err) {
            setError(err.response?.data?.error || 'Invalid credentials');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box
            sx={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'linear-gradient(135deg, #7f5539 0%, #9c6644 50%, #7f5539 100%)',
                padding: 2
            }}
        >
            <Container maxWidth="sm">
                <Paper
                    elevation={10}
                    sx={{
                        padding: 4,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        borderRadius: 3,
                        backgroundColor: '#ede0d4'
                    }}
                >
                    <Box
                        sx={{
                            background: 'linear-gradient(135deg, #7f5539 0%, #9c6644 100%)',
                            borderRadius: '50%',
                            padding: 2,
                            marginBottom: 2
                        }}
                    >
                        <LockIcon sx={{ fontSize: 40, color: '#e6ccb2' }} />
                    </Box>

                    <Typography component="h1" variant="h4" gutterBottom fontWeight="bold" sx={{ color: '#7f5539' }}>
                        Admin Portal
                    </Typography>

                    <Typography variant="body2" sx={{ mb: 3, color: '#9c6644' }}>
                        Jatayu Fraud Detection System
                    </Typography>

                    {error && (
                        <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
                            {error}
                        </Alert>
                    )}

                    <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
                        <TextField
                            required
                            fullWidth
                            label="Username"
                            name="username"
                            autoComplete="username"
                            autoFocus
                            value={credentials.username}
                            onChange={handleChange}
                            sx={{
                                mb: 2,
                                '& .MuiOutlinedInput-root': {
                                    backgroundColor: '#fff',
                                    '&:hover fieldset': { borderColor: '#9c6644' },
                                    '&.Mui-focused fieldset': { borderColor: '#7f5539' }
                                },
                                '& .MuiInputLabel-root.Mui-focused': { color: '#7f5539' }
                            }}
                        />

                        <TextField
                            required
                            fullWidth
                            label="Password"
                            name="password"
                            type="password"
                            autoComplete="current-password"
                            value={credentials.password}
                            onChange={handleChange}
                            sx={{
                                mb: 3,
                                '& .MuiOutlinedInput-root': {
                                    backgroundColor: '#fff',
                                    '&:hover fieldset': { borderColor: '#9c6644' },
                                    '&.Mui-focused fieldset': { borderColor: '#7f5539' }
                                },
                                '& .MuiInputLabel-root.Mui-focused': { color: '#7f5539' }
                            }}
                        />

                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            size="large"
                            disabled={loading}
                            sx={{
                                py: 1.5,
                                textTransform: 'none',
                                fontSize: '1.1rem',
                                fontWeight: 'bold',
                                background: 'linear-gradient(135deg, #7f5539 0%, #9c6644 100%)',
                                color: '#e6ccb2',
                                '&:hover': {
                                    background: 'linear-gradient(135deg, #5c3d2e 0%, #7f5539 100%)'
                                }
                            }}
                        >
                            {loading ? <CircularProgress size={24} sx={{ color: '#e6ccb2' }} /> : 'Sign In'}
                        </Button>
                    </Box>

                    <Typography variant="caption" sx={{ mt: 3, color: '#9c6644' }}>
                        Authorized Personnel Only
                    </Typography>
                </Paper>
            </Container>
        </Box>
    );
};

export default AdminLoginPage;
