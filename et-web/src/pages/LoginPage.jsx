import {
    Box, Container, Paper, Typography, TextField, Button,
    Link, InputAdornment, IconButton, CircularProgress,
} from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api';   // ← src/api.js

export default function LoginPage() {
    const [showPass, setShowPass] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();
    const { register, handleSubmit, formState: { errors } } = useForm();

    const onSubmit = async (data) => {
        setIsLoading(true);
        try {
            const res = await api.post('/login', {
                identifier: data.username,   // backend expects 'identifier'
                password:   data.password,
            });
            
            // Check if account is frozen
            if (res.data.is_frozen) {
                toast.warning(`⚠️ Your account has been frozen: ${res.data.frozen_reason || 'Suspected fraud activity'}`);
            } else {
                toast.success('Login successful! Welcome back.', { icon: '🏦' });
            }
            navigate('/customer-dashboard');
        } catch (err) {
            toast.error(err.response?.data?.message || 'Login failed. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Box
            sx={{
                minHeight: '100vh',
                background: 'linear-gradient(-45deg, #7f5539, #7f5539, #9c6644, #7f5539)',
                backgroundSize: '400% 400%',
                animation: 'gradientShift 12s ease infinite',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                p: 2,
            }}
        >
            <Container maxWidth="xs">
                <Paper
                    elevation={0}
                    sx={{
                        borderRadius: 4,
                        p: { xs: 3.5, sm: 5 },
                        background: 'rgba(255,255,255,0.97)',
                        backdropFilter: 'blur(20px)',
                        boxShadow: '0 25px 80px rgba(127, 85, 57,0.4)',
                    }}
                >
                    {/* Logo */}
                    <Box sx={{ textAlign: 'center', mb: 4 }}>
                        <Box sx={{
                            width: 60, height: 60, mx: 'auto', mb: 2,
                            background: 'linear-gradient(135deg, #7f5539, #9c6644)',
                            borderRadius: 3,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: '0 8px 24px rgba(127, 85, 57,0.3)',
                        }}>
                            <AccountBalanceIcon sx={{ color: '#e6ccb2', fontSize: 30 }} />
                        </Box>
                        <Typography variant="h5" fontWeight={800} color="#7f5539">Welcome Back</Typography>
                        <Typography variant="body2" color="#9c6644" mt={0.5}>
                            Sign in to EagleTrust Bank
                        </Typography>
                    </Box>

                    <Box component="form" onSubmit={handleSubmit(onSubmit)}>
                        <TextField
                            fullWidth
                            label="Customer ID / Email"
                            id="login-username"
                            margin="normal"
                            size="medium"
                            {...register('username', { required: 'Customer ID or Email is required' })}
                            error={!!errors.username}
                            helperText={errors.username?.message}
                        />
                        <TextField
                            fullWidth
                            label="Password"
                            id="login-password"
                            type={showPass ? 'text' : 'password'}
                            margin="normal"
                            size="medium"
                            {...register('password', {
                                required: 'Password is required',
                                minLength: { value: 8, message: 'Minimum 8 characters' },
                            })}
                            error={!!errors.password}
                            helperText={errors.password?.message}
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton onClick={() => setShowPass(!showPass)} edge="end">
                                            {showPass ? <VisibilityOffIcon /> : <VisibilityIcon />}
                                        </IconButton>
                                    </InputAdornment>
                                ),
                            }}
                        />
                        <Box sx={{ textAlign: 'right', mt: 0.5, mb: 2 }}>
                            <Link href="#" underline="hover" sx={{ color: '#7f5539', fontSize: '0.83rem', fontWeight: 500 }}>
                                Forgot Password?
                            </Link>
                        </Box>
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            id="login-submit-btn"
                            size="large"
                            disabled={isLoading}
                            sx={{
                                background: 'linear-gradient(135deg, #7f5539, #9c6644)',
                                color: '#e6ccb2',
                                fontWeight: 700,
                                py: 1.4,
                                '&:hover': { background: 'linear-gradient(135deg, #7f5539, #7f5539)' },
                            }}
                            startIcon={isLoading ? <CircularProgress size={18} color="inherit" /> : null}
                        >
                            {isLoading ? 'Signing in...' : 'Login to Net Banking'}
                        </Button>
                        <Typography variant="body2" sx={{ textAlign: 'center', mt: 3, color: '#9c6644' }}>
                            New customer?{' '}
                            <Link component={RouterLink} to="/register" fontWeight={600} color="#7f5539" underline="hover">
                                Register Now
                            </Link>
                        </Typography>
                    </Box>
                </Paper>

                <Typography variant="caption" sx={{ display: 'block', textAlign: 'center', mt: 3, color: 'rgba(255,255,255,0.4)' }}>
                    🔒 256-bit SSL Encrypted | RBI Licensed | DICGC Insured
                </Typography>
            </Container>
        </Box>
    );
}