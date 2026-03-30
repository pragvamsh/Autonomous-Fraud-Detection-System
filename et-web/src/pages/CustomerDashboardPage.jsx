import {
    Box, Container, Paper, Typography, Grid, Button, Chip,
    CircularProgress, Dialog, DialogTitle, DialogContent,
    DialogActions, TextField, Divider, Avatar, IconButton,
    Tooltip, LinearProgress
} from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import SecurityIcon from '@mui/icons-material/Security';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import AddIcon from '@mui/icons-material/Add';
import HistoryIcon from '@mui/icons-material/History';
import PersonIcon from '@mui/icons-material/Person';
import PaymentIcon from '@mui/icons-material/Payment';
import AssessmentIcon from '@mui/icons-material/Assessment';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import LockIcon from '@mui/icons-material/Lock';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api';
import AccountFrozenBanner from '../components/AccountFrozenBanner';

// ── Colour tokens ─────────────────────────────────────────────────────────────
const C = {
    brown:     '#7f5539',
    brownMid:  '#9c6644',
    brownLight:'#e6ccb2',
    cream:     'rgba(230,204,178,0.15)',
    success:   '#4caf50',
    error:     '#f44336',
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatusBadge({ ok, label }) {
    return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
            {ok
                ? <CheckCircleIcon sx={{ color: C.success, fontSize: 20 }} />
                : <CancelIcon     sx={{ color: C.error,   fontSize: 20 }} />}
            <Typography variant="body2" color={ok ? 'text.primary' : 'text.secondary'}>
                {label}
            </Typography>
        </Box>
    );
}

function ActionButton({ icon, label, onClick, color = C.brown, disabled = false }) {
    return (
        <Button
            fullWidth variant="outlined" startIcon={icon}
            onClick={onClick} disabled={disabled}
            sx={{
                borderColor: color, color: color, fontWeight: 600,
                py: 1.2, borderRadius: 2,
                '&:hover': { bgcolor: `${color}11`, borderColor: color },
            }}
        >
            {label}
        </Button>
    );
}

// ── Add Money Dialog ──────────────────────────────────────────────────────────

function AddMoneyDialog({ open, onClose, onSuccess }) {
    const [amount, setAmount]   = useState('');
    const [loading, setLoading] = useState(false);

    const handleAdd = async () => {
        setLoading(true);
        try {
            const res = await api.post('/account/add-money', { amount: parseFloat(amount) });
            toast.success(res.data.message);
            onSuccess(res.data.new_balance);
            onClose();
            setAmount('');
        } catch (err) {
            const msgs = err.response?.data?.errors || [err.response?.data?.message || 'Failed to add money.'];
            msgs.forEach(m => toast.error(m));
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, p: 1, minWidth: 340 } }}>
            <DialogTitle fontWeight={700} color={C.brown}>Add Money to Account</DialogTitle>
            <DialogContent>
                <Typography variant="body2" color="text.secondary" mb={2}>
                    Enter the amount you want to credit to your account.
                </Typography>
                <TextField
                    fullWidth label="Amount (₹)" type="number"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    inputProps={{ min: 1, max: 100000, step: 0.01 }}
                    helperText="Min ₹1 — Max ₹1,00,000 per transaction"
                />
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
                <Button onClick={onClose} color="inherit">Cancel</Button>
                <Button
                    onClick={handleAdd} variant="contained" disabled={!amount || loading}
                    sx={{ bgcolor: C.brown, '&:hover': { bgcolor: C.brownMid }, fontWeight: 600, minWidth: 120 }}
                    startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <AddIcon />}
                >
                    {loading ? 'Adding...' : 'Add Money'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}

// ── First-Login Security Modal (non-dismissible) ──────────────────────────────

function FirstLoginModal({ open, customerId, onComplete }) {
    const navigate = useNavigate();

    const [step,       setStep]      = useState('SET_PASSWORD');  // SET_PASSWORD → VERIFY_EMAIL → DONE
    const [password,   setPassword]  = useState('');
    const [confirm,    setConfirm]   = useState('');
    const [otp,        setOtp]       = useState('');
    const [otpSent,    setOtpSent]   = useState(false);
    const [loading,    setLoading]   = useState(false);
    const [countdown,  setCountdown] = useState(0);

    // Countdown timer for OTP resend
    useEffect(() => {
        if (countdown <= 0) return;
        const t = setTimeout(() => setCountdown(c => c - 1), 1000);
        return () => clearTimeout(t);
    }, [countdown]);

    const handleSetPassword = async () => {
        setLoading(true);
        try {
            await api.post('/set-password', { password, confirmPassword: confirm });
            toast.success('Password set! Now verify your email.');
            setStep('VERIFY_EMAIL');
        } catch (err) {
            const msgs = err.response?.data?.errors || [err.response?.data?.message || 'Failed to set password.'];
            msgs.forEach(m => toast.error(m));
        } finally {
            setLoading(false);
        }
    };

    const handleSendOtp = async () => {
        setLoading(true);
        try {
            await api.post('/send-otp', { purpose: 'EMAIL_VERIFY' });
            toast.success('OTP sent to your registered email!');
            setOtpSent(true);
            setCountdown(60);
        } catch (err) {
            toast.error(err.response?.data?.message || 'Failed to send OTP.');
        } finally {
            setLoading(false);
        }
    };

    const handleVerifyOtp = async () => {
        setLoading(true);
        try {
            await api.post('/verify-email-otp', { otp });
            toast.success('Email verified! Welcome to EagleTrust Bank 🎉');
            onComplete();
        } catch (err) {
            toast.error(err.response?.data?.message || 'OTP verification failed.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog
            open={open}
            disableEscapeKeyDown
            onClose={(_, reason) => { if (reason !== 'backdropClick' && reason !== 'escapeKeyDown') return; }}
            PaperProps={{ sx: { borderRadius: 3, p: 1, minWidth: 380, maxWidth: 440 } }}
        >
            <DialogTitle fontWeight={700} color={C.brown} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SecurityIcon /> Complete Your Security Setup
            </DialogTitle>
            <DialogContent>
                {/* Progress indicator */}
                <Box sx={{ mb: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="caption" color={step === 'SET_PASSWORD' ? C.brown : C.success} fontWeight={700}>
                            {step === 'SET_PASSWORD' ? '● ' : '✔ '}Set Password
                        </Typography>
                        <Typography variant="caption" color={step === 'VERIFY_EMAIL' ? C.brown : step === 'DONE' ? C.success : 'text.disabled'} fontWeight={700}>
                            {step === 'DONE' ? '✔ ' : '● '}Verify Email
                        </Typography>
                    </Box>
                    <LinearProgress
                        variant="determinate"
                        value={step === 'SET_PASSWORD' ? 25 : 75}
                        sx={{ borderRadius: 1, bgcolor: '#e0c8b0', '& .MuiLinearProgress-bar': { bgcolor: C.brown } }}
                    />
                </Box>

                <Typography variant="body2" color="text.secondary" mb={2}>
                    {step === 'SET_PASSWORD'
                        ? 'Your account was created without a password. Set a strong password to secure your account.'
                        : 'Verify your email address to complete setup and unlock full dashboard access.'}
                </Typography>

                {step === 'SET_PASSWORD' && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            fullWidth label="New Password" type="password"
                            value={password} onChange={e => setPassword(e.target.value)}
                            helperText="Min 8 chars, uppercase, lowercase, digit, special character"
                        />
                        <TextField
                            fullWidth label="Confirm Password" type="password"
                            value={confirm} onChange={e => setConfirm(e.target.value)}
                            error={confirm.length > 0 && password !== confirm}
                            helperText={confirm.length > 0 && password !== confirm ? 'Passwords do not match' : ''}
                        />
                    </Box>
                )}

                {step === 'VERIFY_EMAIL' && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {!otpSent ? (
                            <Typography variant="body2">
                                Click below to receive a 6-digit OTP on your registered email address.
                            </Typography>
                        ) : (
                            <TextField
                                fullWidth label="Enter 6-digit OTP" value={otp}
                                onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                inputProps={{ maxLength: 6 }}
                                helperText="OTP valid for 10 minutes"
                            />
                        )}
                        {otpSent && (
                            <Button
                                size="small" disabled={countdown > 0 || loading}
                                onClick={handleSendOtp}
                                sx={{ color: C.brownMid, textTransform: 'none', alignSelf: 'flex-start' }}
                            >
                                {countdown > 0 ? `Resend OTP in ${countdown}s` : 'Resend OTP'}
                            </Button>
                        )}
                    </Box>
                )}
            </DialogContent>

            <DialogActions sx={{ px: 3, pb: 2, flexDirection: 'column', gap: 1 }}>
                {step === 'SET_PASSWORD' && (
                    <Button
                        fullWidth variant="contained" disabled={!password || !confirm || loading}
                        onClick={handleSetPassword}
                        sx={{ bgcolor: C.brown, '&:hover': { bgcolor: C.brownMid }, fontWeight: 700, py: 1.2 }}
                        startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <LockIcon />}
                    >
                        {loading ? 'Setting Password...' : 'Set Password'}
                    </Button>
                )}
                {step === 'VERIFY_EMAIL' && !otpSent && (
                    <Button
                        fullWidth variant="contained" disabled={loading}
                        onClick={handleSendOtp}
                        sx={{ bgcolor: C.brown, '&:hover': { bgcolor: C.brownMid }, fontWeight: 700, py: 1.2 }}
                        startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
                    >
                        {loading ? 'Sending...' : 'Send OTP to Email'}
                    </Button>
                )}
                {step === 'VERIFY_EMAIL' && otpSent && (
                    <Button
                        fullWidth variant="contained"
                        disabled={otp.length !== 6 || loading}
                        onClick={handleVerifyOtp}
                        sx={{ bgcolor: C.brown, '&:hover': { bgcolor: C.brownMid }, fontWeight: 700, py: 1.2 }}
                        startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
                    >
                        {loading ? 'Verifying...' : 'Verify Email'}
                    </Button>
                )}
                <Typography variant="caption" color="text.secondary" textAlign="center">
                    🔒 You cannot access the dashboard until this is complete.
                </Typography>
            </DialogActions>
        </Dialog>
    );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function CustomerDashboard() {
    const navigate = useNavigate();
    const [profile,        setProfile]       = useState(null);
    const [loading,        setLoading]       = useState(true);
    const [showAddMoney,   setShowAddMoney]  = useState(false);
    const [showFirstLogin, setShowFirstLogin]= useState(false);
    const [recentTransactions, setRecentTransactions] = useState([]);

    const fetchProfile = useCallback(async () => {
        try {
            const [profileRes, txnRes] = await Promise.all([
                api.get('/me'),
                api.get('/transactions?limit=5')
            ]);
            setProfile(profileRes.data);
            setRecentTransactions(txnRes.data.transactions || []);
            if (!profileRes.data.security_complete) setShowFirstLogin(true);
        } catch {
            toast.error('Failed to load profile.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchProfile(); }, [fetchProfile]);

    const handleSecurityComplete = () => {
        setShowFirstLogin(false);
        fetchProfile();
        toast.success('Security setup complete! Welcome to your dashboard 🎉');
    };

    const handleBalanceUpdate = (newBalance) => {
        setProfile(prev => ({ ...prev, balance: newBalance }));
    };

    const handleCopyAccountNumber = () => {
        navigator.clipboard.writeText(profile.account_number_raw || profile.account_number);
        toast.info('Account number copied!', { autoClose: 1500 });
    };

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', bgcolor: '#fdf6ef' }}>
                <CircularProgress sx={{ color: C.brown }} />
            </Box>
        );
    }

    const securityLocked = profile && !profile.security_complete;

    return (
        <Box sx={{ minHeight: '100vh', bgcolor: '#fdf6ef', pb: 6 }}>

            {/* Header */}
            <Box sx={{ bgcolor: C.brown, color: C.brownLight, py: 2.5, px: 3 }}>
                <Container maxWidth="md">
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                            <AccountBalanceIcon />
                            <Typography fontWeight={800} fontSize={18}>EagleTrust Bank</Typography>
                        </Box>
                        <Button
                            size="small" variant="outlined"
                            sx={{ color: C.brownLight, borderColor: C.brownLight, '&:hover': { bgcolor: 'rgba(230,204,178,0.1)' } }}
                            onClick={async () => {
                                await api.post('/logout');
                                navigate('/login');
                            }}
                        >
                            Logout
                        </Button>
                    </Box>
                </Container>
            </Box>

            <Container maxWidth="md" sx={{ mt: 4 }}>

                {/* Account Frozen Banner */}
                {profile?.is_frozen && (
                    <AccountFrozenBanner
                        reason={profile.frozen_reason}
                        frozenAt={profile.frozen_at}
                        alertId={profile.frozen_by_alert_id}
                        onContactSupport={() => {
                            toast.info('Please call 1800-XXX-XXXX for immediate assistance');
                        }}
                    />
                )}

                <Grid container spacing={3}>

                    {/* Welcome + Account Summary */}
                    <Grid item xs={12}>
                        <Paper elevation={0} sx={{ borderRadius: 3, p: 3.5, boxShadow: '0 4px 24px rgba(127,85,57,0.1)' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2.5 }}>
                                <Avatar sx={{ bgcolor: C.brown, width: 52, height: 52, fontSize: 22 }}>
                                    {profile?.full_name?.[0]?.toUpperCase()}
                                </Avatar>
                                <Box>
                                    <Typography variant="h6" fontWeight={800} color={C.brown}>
                                        Welcome, {profile?.full_name?.split(' ')[0]}!
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        Member since {new Date(profile?.member_since).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
                                    </Typography>
                                </Box>
                                <Chip
                                    label={profile?.account_type?.toUpperCase()}
                                    size="small"
                                    sx={{ ml: 'auto', bgcolor: C.cream, color: C.brown, fontWeight: 700, border: `1px solid ${C.brownLight}` }}
                                />
                            </Box>

                            <Divider sx={{ mb: 2.5, borderColor: '#f0e0d0' }} />

                            <Grid container spacing={3}>
                                {/* Balance */}
                                <Grid item xs={12} sm={6}>
                                    <Box sx={{ bgcolor: `${C.brown}0d`, borderRadius: 2, p: 2.5 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                            <AccountBalanceWalletIcon sx={{ color: C.brownMid, fontSize: 20 }} />
                                            <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase" letterSpacing={1}>
                                                Available Balance
                                            </Typography>
                                        </Box>
                                        <Typography variant="h4" fontWeight={800} color={C.brown}>
                                            ₹{(profile?.balance ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                        </Typography>
                                    </Box>
                                </Grid>

                                {/* Account Number */}
                                <Grid item xs={12} sm={6}>
                                    <Box sx={{ bgcolor: '#f9f4f0', borderRadius: 2, p: 2.5 }}>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase" letterSpacing={1} display="block" mb={1}>
                                            Account Number
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography variant="h6" fontWeight={700} color="#555" letterSpacing={2}>
                                                {profile?.account_number}
                                            </Typography>
                                            <Tooltip title="Copy">
                                                <IconButton size="small" onClick={handleCopyAccountNumber}>
                                                    <ContentCopyIcon sx={{ fontSize: 16, color: C.brownMid }} />
                                                </IconButton>
                                            </Tooltip>
                                        </Box>
                                        <Typography variant="caption" color="text.secondary">
                                            Customer ID: {profile?.customer_id}
                                        </Typography>
                                    </Box>
                                </Grid>
                            </Grid>
                        </Paper>
                    </Grid>

                    {/* Security Status */}
                    <Grid item xs={12} sm={5}>
                        <Paper elevation={0} sx={{ borderRadius: 3, p: 3, boxShadow: '0 4px 24px rgba(127,85,57,0.08)', height: '100%' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <SecurityIcon sx={{ color: C.brown }} />
                                <Typography fontWeight={700} color={C.brown}>Security Status</Typography>
                            </Box>
                            <StatusBadge ok={profile?.is_email_verified} label="Email Verified" />
                            <StatusBadge ok={profile?.password_set}      label="Password Set" />
                            <StatusBadge ok={profile?.security_complete}  label="Account Secured" />

                            {!profile?.security_complete && (
                                <Button
                                    fullWidth variant="contained" size="small" sx={{ mt: 2, bgcolor: C.brown, fontWeight: 700 }}
                                    onClick={() => setShowFirstLogin(true)}
                                    startIcon={<LockIcon />}
                                >
                                    Complete Setup
                                </Button>
                            )}
                        </Paper>
                    </Grid>

                    {/* Action Buttons */}
                    <Grid item xs={12} sm={7}>
                        <Paper elevation={0} sx={{ borderRadius: 3, p: 3, boxShadow: '0 4px 24px rgba(127,85,57,0.08)' }}>
                            <Typography fontWeight={700} color={C.brown} mb={2}>Quick Actions</Typography>
                            <Grid container spacing={1.5}>
                                {[
                                    { icon: <AddIcon />,        label: 'Add Money',          action: () => setShowAddMoney(true),           disabled: securityLocked },
                                    { icon: <PaymentIcon />,    label: 'Make Payment',        action: () => navigate('/payment'),            disabled: securityLocked || profile?.is_frozen },
                                    { icon: <HistoryIcon />,    label: 'Transaction History', action: () => navigate('/transactions'),       disabled: securityLocked },
                                    { icon: <AssessmentIcon />, label: 'Risk Evaluation',     action: () => navigate('/risk'),              disabled: securityLocked },
                                    { icon: <PersonIcon />,     label: 'Update Profile',      action: () => navigate('/profile'),           disabled: false },
                                ].map(({ icon, label, action, disabled }) => (
                                    <Grid item xs={12} sm={6} key={label}>
                                        <ActionButton icon={icon} label={label} onClick={action} disabled={disabled} />
                                    </Grid>
                                ))}
                            </Grid>
                            {securityLocked && (
                                <Typography variant="caption" color={C.error} display="block" mt={1.5}>
                                    ⚠️ Complete security setup to unlock all features.
                                </Typography>
                            )}
                        </Paper>
                    </Grid>

                    {/* Recent Transactions */}
                    <Grid item xs={12}>
                        <Paper elevation={0} sx={{ borderRadius: 3, p: 3, boxShadow: '0 4px 24px rgba(127,85,57,0.08)' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                                <Typography fontWeight={700} color={C.brown}>Recent Transactions</Typography>
                                <Button
                                    size="small"
                                    endIcon={<ArrowForwardIcon />}
                                    onClick={() => navigate('/transactions')}
                                    disabled={securityLocked}
                                    sx={{
                                        color: C.brownMid,
                                        textTransform: 'none',
                                        '&:hover': { bgcolor: C.cream }
                                    }}
                                >
                                    View All
                                </Button>
                            </Box>
                            <Divider sx={{ mb: 2, borderColor: '#f0e0d0' }} />

                            {recentTransactions.length === 0 ? (
                                <Typography variant="body2" color="text.secondary" textAlign="center" py={3}>
                                    No transactions yet. Add money or make a payment to get started!
                                </Typography>
                            ) : (
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                                    {recentTransactions.map(txn => (
                                        <Box
                                            key={txn.transaction_id}
                                            sx={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                p: 1.5,
                                                borderRadius: 1.5,
                                                bgcolor: '#fafafa',
                                                border: '1px solid #f0e0d0',
                                                '&:hover': { bgcolor: C.cream }
                                            }}
                                        >
                                            <Box>
                                                <Typography variant="body2" fontWeight={600}>
                                                    {txn.description}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {new Date(txn.created_at).toLocaleDateString('en-IN', {
                                                        year: 'numeric',
                                                        month: 'short',
                                                        day: 'numeric',
                                                    })}
                                                </Typography>
                                            </Box>
                                            <Box sx={{ textAlign: 'right' }}>
                                                <Typography
                                                    variant="body2"
                                                    fontWeight={700}
                                                    color={txn.type === 'CREDIT' ? C.success : C.brown}
                                                >
                                                    {txn.type === 'CREDIT' ? '+' : '-'}₹{txn.amount.toLocaleString('en-IN', {
                                                        minimumFractionDigits: 2,
                                                        maximumFractionDigits: 2
                                                    })}
                                                </Typography>
                                                <Chip
                                                    label={txn.type}
                                                    size="small"
                                                    sx={{
                                                        fontSize: 9,
                                                        height: 18,
                                                        bgcolor: txn.type === 'CREDIT' ? `${C.success}15` : C.cream,
                                                        color: txn.type === 'CREDIT' ? C.success : C.brown,
                                                        fontWeight: 600,
                                                        mt: 0.5
                                                    }}
                                                />
                                            </Box>
                                        </Box>
                                    ))}
                                </Box>
                            )}
                        </Paper>
                    </Grid>

                </Grid>
            </Container>

            {/* Modals */}
            <FirstLoginModal
                open={showFirstLogin}
                customerId={profile?.customer_id}
                onComplete={handleSecurityComplete}
            />
            <AddMoneyDialog
                open={showAddMoney}
                onClose={() => setShowAddMoney(false)}
                onSuccess={handleBalanceUpdate}
            />
        </Box>
    );
}