import { useState } from 'react';
import {
    Dialog, DialogContent, Box, Typography, Button, Chip,
    CircularProgress, TextField
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import api from '../api';
import { toast } from 'react-toastify';

const C = {
    brown: '#7f5539',
    brownMid: '#9c6644',
    brownLight: '#e6ccb2',
    cream: 'rgba(230,204,178,0.15)',
    bg: '#fdf6ef',
    success: '#4caf50',
    error: '#f44336',
    warning: '#ff9800',
    info: '#1976d2',
};

/**
 * FlagConfirmationModal - Handles FLAG verdict confirmation flow
 *
 * Shows when a transaction is flagged (score 26-50):
 * - Score 26-44: Simple CONFIRM / NOT ME buttons
 * - Score 45-50: OTP verification required (MFA)
 */
export default function FlagConfirmationModal({
    open,
    onClose,
    paymentId,
    amount,
    recipient,
    score,
    requiresMfa = false,
    onConfirm,
    onDispute,
}) {
    const [loading, setLoading] = useState(false);
    const [step, setStep] = useState('confirm'); // 'confirm' | 'otp' | 'done'
    const [otp, setOtp] = useState('');
    const [otpError, setOtpError] = useState('');
    const [result, setResult] = useState(null); // 'confirmed' | 'disputed' | 'escalated'

    const handleConfirm = async () => {
        if (requiresMfa) {
            // Need OTP verification first
            setStep('otp');
            try {
                await api.post('/send-otp', { purpose: 'FRAUD_MFA' });
                toast.info('OTP sent to your registered email');
            } catch (err) {
                toast.error('Failed to send OTP');
            }
            return;
        }

        setLoading(true);
        try {
            await api.post(`/aba/confirm/${paymentId}`, { action: 'CONFIRM' });
            setResult('confirmed');
            setStep('done');
            toast.success('Transaction confirmed successfully');
            onConfirm?.();
        } catch (err) {
            toast.error('Failed to confirm transaction');
        } finally {
            setLoading(false);
        }
    };

    const handleDispute = async () => {
        setLoading(true);
        try {
            await api.post(`/aba/confirm/${paymentId}`, { action: 'NOT_ME' });
            setResult('disputed');
            setStep('done');
            toast.info('Transaction reported and escalated for review');
            onDispute?.();
        } catch (err) {
            toast.error('Failed to report transaction');
        } finally {
            setLoading(false);
        }
    };

    const handleVerifyOtp = async () => {
        if (otp.length !== 6) {
            setOtpError('Please enter a 6-digit OTP');
            return;
        }

        setLoading(true);
        setOtpError('');
        try {
            const res = await api.post('/aba/verify-otp', {
                otp,
                payment_id: paymentId,
            });

            if (res.data?.verified) {
                setResult('confirmed');
                setStep('done');
                toast.success('Transaction verified and approved');
                onConfirm?.();
            } else {
                setOtpError('Invalid OTP. Transaction escalated for review.');
                setResult('escalated');
                setStep('done');
            }
        } catch (err) {
            setOtpError('Verification failed');
            toast.error('OTP verification failed');
        } finally {
            setLoading(false);
        }
    };

    const renderConfirmStep = () => (
        <>
            <Box sx={{ textAlign: 'center', mb: 3 }}>
                <WarningAmberIcon sx={{ fontSize: 64, color: C.warning, mb: 1 }} />
                <Typography variant="h6" fontWeight={700} color={C.brown}>
                    Confirm This Transaction
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    We detected unusual activity. Please verify this transaction.
                </Typography>
            </Box>

            <Box sx={{
                p: 2, borderRadius: 2,
                bgcolor: '#fff8e1',
                border: '1px solid #ffe082',
                mb: 3,
            }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">Amount</Typography>
                    <Typography variant="body2" fontWeight={700} color={C.brown}>
                        {amount}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">Recipient</Typography>
                    <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
                        {recipient}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Risk Score</Typography>
                    <Chip label={score} size="small"
                        sx={{ bgcolor: C.warning, color: 'white', fontWeight: 700, fontSize: 11 }} />
                </Box>
            </Box>

            {requiresMfa && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mb: 2 }}>
                    High-risk transaction requires OTP verification
                </Typography>
            )}

            <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                    fullWidth
                    variant="contained"
                    color="success"
                    onClick={handleConfirm}
                    disabled={loading}
                    startIcon={loading ? <CircularProgress size={16} /> : <CheckCircleIcon />}
                    sx={{ py: 1.5, fontWeight: 700 }}
                >
                    {requiresMfa ? 'Verify with OTP' : 'Yes, This Was Me'}
                </Button>
                <Button
                    fullWidth
                    variant="outlined"
                    color="error"
                    onClick={handleDispute}
                    disabled={loading}
                    startIcon={<ReportProblemIcon />}
                    sx={{ py: 1.5, fontWeight: 700 }}
                >
                    Not Me
                </Button>
            </Box>
        </>
    );

    const renderOtpStep = () => (
        <>
            <Box sx={{ textAlign: 'center', mb: 3 }}>
                <Typography variant="h6" fontWeight={700} color={C.brown}>
                    Enter Verification Code
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    We sent a 6-digit code to your registered email
                </Typography>
            </Box>

            <TextField
                fullWidth
                label="OTP Code"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                error={!!otpError}
                helperText={otpError}
                inputProps={{ maxLength: 6, style: { textAlign: 'center', letterSpacing: 8, fontSize: 24 } }}
                sx={{ mb: 3 }}
            />

            <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                    fullWidth
                    variant="contained"
                    onClick={handleVerifyOtp}
                    disabled={loading || otp.length !== 6}
                    sx={{ py: 1.5, fontWeight: 700, bgcolor: C.brown }}
                >
                    {loading ? <CircularProgress size={20} /> : 'Verify'}
                </Button>
                <Button
                    fullWidth
                    variant="outlined"
                    onClick={() => setStep('confirm')}
                    disabled={loading}
                    sx={{ py: 1.5, fontWeight: 700 }}
                >
                    Back
                </Button>
            </Box>
        </>
    );

    const renderDoneStep = () => (
        <Box sx={{ textAlign: 'center', py: 2 }}>
            {result === 'confirmed' ? (
                <>
                    <CheckCircleIcon sx={{ fontSize: 64, color: C.success, mb: 1 }} />
                    <Typography variant="h6" fontWeight={700} color={C.success}>
                        Transaction Confirmed
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Your payment has been approved successfully.
                    </Typography>
                </>
            ) : result === 'disputed' ? (
                <>
                    <ReportProblemIcon sx={{ fontSize: 64, color: C.error, mb: 1 }} />
                    <Typography variant="h6" fontWeight={700} color={C.error}>
                        Transaction Reported
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        We've escalated this for investigation. Your account is secured.
                    </Typography>
                </>
            ) : (
                <>
                    <WarningAmberIcon sx={{ fontSize: 64, color: C.warning, mb: 1 }} />
                    <Typography variant="h6" fontWeight={700} color={C.warning}>
                        Verification Failed
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Transaction escalated to our fraud team for review.
                    </Typography>
                </>
            )}

            <Button
                variant="contained"
                onClick={onClose}
                sx={{ mt: 3, px: 4, py: 1.5, fontWeight: 700, bgcolor: C.brown }}
            >
                Close
            </Button>
        </Box>
    );

    return (
        <Dialog
            open={open}
            maxWidth="xs"
            fullWidth
            onClose={step === 'done' ? onClose : undefined}
            PaperProps={{
                sx: {
                    borderRadius: 3,
                    overflow: 'hidden',
                    background: 'linear-gradient(160deg, #fffcf9 0%, #fdf6ef 100%)',
                }
            }}
        >
            <DialogContent sx={{ p: 3 }}>
                {step === 'confirm' && renderConfirmStep()}
                {step === 'otp' && renderOtpStep()}
                {step === 'done' && renderDoneStep()}
            </DialogContent>
        </Dialog>
    );
}
