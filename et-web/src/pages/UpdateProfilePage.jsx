import {
    Box, Container, Paper, Typography, TextField, Button,
    Divider, Grid, CircularProgress, Chip
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api';

const C = { brown: '#7f5539', brownMid: '#9c6644', brownLight: '#e6ccb2' };

function SectionCard({ title, children }) {
    return (
        <Paper elevation={0} sx={{ borderRadius: 3, p: 3, mb: 2.5, boxShadow: '0 4px 24px rgba(127,85,57,0.08)' }}>
            <Typography fontWeight={700} color={C.brown} mb={2}>{title}</Typography>
            <Divider sx={{ mb: 2.5, borderColor: '#f0e0d0' }} />
            {children}
        </Paper>
    );
}

function ReadOnlyField({ label, value }) {
    return (
        <TextField
            fullWidth label={label} value={value || '—'} size="small"
            InputProps={{ readOnly: true }}
            sx={{ mb: 1.5, '& .MuiInputBase-input': { color: '#777' } }}
        />
    );
}

export default function UpdateProfile() {
    const navigate     = useNavigate();
    const [profile,    setProfile]    = useState(null);
    const [loading,    setLoading]    = useState(true);

    // Email change state
    const [newEmail,      setNewEmail]      = useState('');
    const [emailOtp,      setEmailOtp]      = useState('');
    const [emailOtpSent,  setEmailOtpSent]  = useState(false);
    const [emailCountdown,setEmailCountdown]= useState(0);
    const [emailLoading,  setEmailLoading]  = useState(false);

    // Phone change state
    const [newPhone,    setNewPhone]    = useState('');
    const [phoneLoading,setPhoneLoading]= useState(false);

    // Password change state
    const [newPassword, setNewPassword] = useState('');
    const [confirmPw,   setConfirmPw]   = useState('');
    const [pwOtp,       setPwOtp]       = useState('');
    const [pwOtpSent,   setPwOtpSent]   = useState(false);
    const [pwCountdown, setPwCountdown] = useState(0);
    const [pwLoading,   setPwLoading]   = useState(false);

    useEffect(() => {
        api.get('/me').then(r => setProfile(r.data)).catch(() => toast.error('Failed to load profile.')).finally(() => setLoading(false));
    }, []);

    // Countdown helpers
    useEffect(() => {
        if (emailCountdown <= 0) return;
        const t = setTimeout(() => setEmailCountdown(c => c - 1), 1000);
        return () => clearTimeout(t);
    }, [emailCountdown]);

    useEffect(() => {
        if (pwCountdown <= 0) return;
        const t = setTimeout(() => setPwCountdown(c => c - 1), 1000);
        return () => clearTimeout(t);
    }, [pwCountdown]);

    // ── Email OTP ──
    const sendEmailOtp = async () => {
        setEmailLoading(true);
        try {
            await api.post('/send-otp', { purpose: 'EMAIL_VERIFY' });
            toast.success('OTP sent to your current email.');
            setEmailOtpSent(true);
            setEmailCountdown(60);
        } catch (err) { toast.error(err.response?.data?.message || 'Failed to send OTP.'); }
        finally { setEmailLoading(false); }
    };

    const submitEmailChange = async () => {
        setEmailLoading(true);
        try {
            await api.post('/profile/update-email', { newEmail, otp: emailOtp });
            toast.success('Email updated. Please verify your new email.');
            setProfile(p => ({ ...p, email: newEmail, is_email_verified: false }));
            setNewEmail(''); setEmailOtp(''); setEmailOtpSent(false);
        } catch (err) { toast.error(err.response?.data?.message || 'Failed to update email.'); }
        finally { setEmailLoading(false); }
    };

    // ── Phone ──
    const submitPhoneChange = async () => {
        setPhoneLoading(true);
        try {
            await api.post('/profile/update-phone', { newPhone });
            toast.success('Phone number updated.');
            setProfile(p => ({ ...p, phone_number: newPhone }));
            setNewPhone('');
        } catch (err) { toast.error(err.response?.data?.message || 'Failed to update phone.'); }
        finally { setPhoneLoading(false); }
    };

    // ── Password OTP ──
    const sendPwOtp = async () => {
        setPwLoading(true);
        try {
            await api.post('/send-otp', { purpose: 'PASSWORD_CHANGE' });
            toast.success('OTP sent to your email.');
            setPwOtpSent(true);
            setPwCountdown(60);
        } catch (err) { toast.error(err.response?.data?.message || 'Failed to send OTP.'); }
        finally { setPwLoading(false); }
    };

    const submitPasswordChange = async () => {
        if (newPassword !== confirmPw) { toast.error('Passwords do not match.'); return; }
        setPwLoading(true);
        try {
            await api.post('/change-password', { otp: pwOtp, newPassword, confirmPassword: confirmPw });
            toast.success('Password changed successfully.');
            setNewPassword(''); setConfirmPw(''); setPwOtp(''); setPwOtpSent(false);
        } catch (err) {
            const msgs = err.response?.data?.errors || [err.response?.data?.message || 'Failed.'];
            msgs.forEach(m => toast.error(m));
        } finally { setPwLoading(false); }
    };

    if (loading) return (
        <Box sx={{ display:'flex', justifyContent:'center', alignItems:'center', minHeight:'100vh', bgcolor:'#fdf6ef' }}>
            <CircularProgress sx={{ color: C.brown }} />
        </Box>
    );

    return (
        <Box sx={{ minHeight: '100vh', bgcolor: '#fdf6ef', pb: 6 }}>
            {/* Header */}
            <Box sx={{ bgcolor: C.brown, color: C.brownLight, py: 2, px: 3 }}>
                <Container maxWidth="md">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/dashboard')}
                            sx={{ color: C.brownLight, textTransform: 'none', fontWeight: 600 }}>
                            Dashboard
                        </Button>
                        <Typography fontWeight={700} fontSize={17} ml={1}>Update Profile</Typography>
                    </Box>
                </Container>
            </Box>

            <Container maxWidth="md" sx={{ mt: 4 }}>

                {/* Read-Only Info */}
                <SectionCard title="Account Information (Read-Only)">
                    <Grid container spacing={2}>
                        {[
                            ['Full Name',      profile?.full_name],
                            ['Customer ID',    profile?.customer_id],
                            ['Account Number', profile?.account_number],
                            ['Account Type',   profile?.account_type?.toUpperCase()],
                            ['Date of Birth',  profile?.date_of_birth],
                            ['Gender',         profile?.gender?.charAt(0).toUpperCase() + profile?.gender?.slice(1)],
                        ].map(([label, value]) => (
                            <Grid item xs={12} sm={6} key={label}>
                                <ReadOnlyField label={label} value={value} />
                            </Grid>
                        ))}
                    </Grid>
                    <Typography variant="caption" color="text.secondary">
                        These fields are permanent and cannot be changed.
                    </Typography>
                </SectionCard>

                {/* Email Change */}
                <SectionCard title="Change Email Address">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <Typography variant="body2">Current: <b>{profile?.email}</b></Typography>
                        <Chip
                            size="small"
                            label={profile?.is_email_verified ? 'Verified' : 'Unverified'}
                            sx={{ bgcolor: profile?.is_email_verified ? '#e8f5e9' : '#fff3e0',
                                  color: profile?.is_email_verified ? '#2e7d32' : '#e65100', fontWeight: 600 }}
                        />
                    </Box>
                    <TextField
                        fullWidth label="New Email Address" type="email" size="small"
                        value={newEmail} onChange={e => setNewEmail(e.target.value)}
                        sx={{ mb: 2 }}
                    />
                    {emailOtpSent && (
                        <TextField
                            fullWidth label="Enter OTP" size="small" sx={{ mb: 2 }}
                            value={emailOtp} onChange={e => setEmailOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                            inputProps={{ maxLength: 6 }}
                        />
                    )}
                    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
                        <Button variant="outlined" size="small" disabled={emailCountdown > 0 || emailLoading}
                            onClick={sendEmailOtp}
                            sx={{ borderColor: C.brown, color: C.brown, fontWeight: 600 }}>
                            {emailCountdown > 0 ? `Resend in ${emailCountdown}s` : emailOtpSent ? 'Resend OTP' : 'Send OTP'}
                        </Button>
                        {emailOtpSent && (
                            <Button variant="contained" size="small"
                                disabled={!newEmail || emailOtp.length !== 6 || emailLoading}
                                onClick={submitEmailChange}
                                startIcon={emailLoading ? <CircularProgress size={14} color="inherit" /> : null}
                                sx={{ bgcolor: C.brown, fontWeight: 600 }}>
                                Update Email
                            </Button>
                        )}
                    </Box>
                </SectionCard>

                {/* Phone Change */}
                <SectionCard title="Change Phone Number">
                    <Typography variant="body2" mb={2}>Current: <b>{profile?.phone_number}</b></Typography>
                    <TextField
                        fullWidth label="New Phone Number" size="small" sx={{ mb: 2 }}
                        value={newPhone} onChange={e => setNewPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                        inputProps={{ maxLength: 10 }}
                        helperText="Must be a valid 10-digit Indian mobile number starting with 6–9"
                    />
                    <Button variant="contained" size="small"
                        disabled={newPhone.length !== 10 || phoneLoading}
                        onClick={submitPhoneChange}
                        startIcon={phoneLoading ? <CircularProgress size={14} color="inherit" /> : null}
                        sx={{ bgcolor: C.brown, fontWeight: 600 }}>
                        Update Phone
                    </Button>
                </SectionCard>

                {/* Password Change */}
                <SectionCard title="Change Password">
                    <TextField fullWidth label="New Password" type="password" size="small"
                        value={newPassword} onChange={e => setNewPassword(e.target.value)} sx={{ mb: 2 }}
                        helperText="Min 8 chars, uppercase, lowercase, digit, special character"
                    />
                    <TextField fullWidth label="Confirm New Password" type="password" size="small"
                        value={confirmPw} onChange={e => setConfirmPw(e.target.value)}
                        error={confirmPw.length > 0 && newPassword !== confirmPw}
                        helperText={confirmPw.length > 0 && newPassword !== confirmPw ? 'Passwords do not match' : ''}
                        sx={{ mb: 2 }}
                    />
                    {pwOtpSent && (
                        <TextField fullWidth label="Enter OTP" size="small" sx={{ mb: 2 }}
                            value={pwOtp} onChange={e => setPwOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                            inputProps={{ maxLength: 6 }}
                        />
                    )}
                    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
                        <Button variant="outlined" size="small" disabled={pwCountdown > 0 || pwLoading}
                            onClick={sendPwOtp}
                            sx={{ borderColor: C.brown, color: C.brown, fontWeight: 600 }}>
                            {pwCountdown > 0 ? `Resend in ${pwCountdown}s` : pwOtpSent ? 'Resend OTP' : 'Send OTP'}
                        </Button>
                        {pwOtpSent && (
                            <Button variant="contained" size="small"
                                disabled={!newPassword || !confirmPw || pwOtp.length !== 6 || pwLoading}
                                onClick={submitPasswordChange}
                                startIcon={pwLoading ? <CircularProgress size={14} color="inherit" /> : null}
                                sx={{ bgcolor: C.brown, fontWeight: 600 }}>
                                Change Password
                            </Button>
                        )}
                    </Box>
                </SectionCard>

            </Container>
        </Box>
    );
}