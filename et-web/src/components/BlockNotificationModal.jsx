import {
    Dialog, DialogContent, Box, Typography, Button, Chip, Divider
} from '@mui/material';
import BlockIcon from '@mui/icons-material/Block';
import SecurityIcon from '@mui/icons-material/Security';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

const C = {
    brown: '#7f5539',
    brownMid: '#9c6644',
    brownLight: '#e6ccb2',
    error: '#f44336',
    errorLight: '#ffebee',
};

/**
 * BlockNotificationModal - Displays BLOCK verdict notification
 *
 * Shows when a transaction has been blocked due to high fraud risk:
 * - Transaction blocked message
 * - Account freeze warning (if applicable)
 * - Support contact information
 * - Next steps for the customer
 */
export default function BlockNotificationModal({
    open,
    onClose,
    paymentId,
    amount,
    recipient,
    score,
    accountFrozen = false,
    caseId,
    typology,
}) {
    return (
        <Dialog
            open={open}
            maxWidth="xs"
            fullWidth
            onClose={onClose}
            PaperProps={{
                sx: {
                    borderRadius: 3,
                    overflow: 'hidden',
                    background: 'linear-gradient(160deg, #fff5f5 0%, #ffebee 100%)',
                    border: '2px solid #f4433640',
                }
            }}
        >
            <DialogContent sx={{ p: 0 }}>
                {/* Header */}
                <Box sx={{
                    bgcolor: C.error,
                    px: 3, py: 2.5,
                    textAlign: 'center',
                }}>
                    <BlockIcon sx={{ fontSize: 48, color: 'white', mb: 1 }} />
                    <Typography variant="h6" fontWeight={800} color="white">
                        Transaction Blocked
                    </Typography>
                    <Typography variant="body2" color="rgba(255,255,255,0.85)">
                        This transaction has been stopped for your protection
                    </Typography>
                </Box>

                <Box sx={{ p: 3 }}>
                    {/* Transaction Details */}
                    <Box sx={{
                        p: 2, borderRadius: 2,
                        bgcolor: 'white',
                        border: '1px solid #f4433630',
                        mb: 2,
                    }}>
                        <Typography variant="caption" fontWeight={700} color="text.secondary"
                            textTransform="uppercase" letterSpacing={0.5}>
                            Blocked Transaction
                        </Typography>
                        <Box sx={{ mt: 1.5 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                                <Typography variant="body2" color="text.secondary">Amount</Typography>
                                <Typography variant="body2" fontWeight={700} color={C.error}>
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
                                <Chip label={`${score}/100`} size="small"
                                    sx={{ bgcolor: C.error, color: 'white', fontWeight: 700, fontSize: 11 }} />
                            </Box>
                        </Box>
                    </Box>

                    {/* Account Frozen Warning */}
                    {accountFrozen && (
                        <Box sx={{
                            p: 2, borderRadius: 2,
                            bgcolor: '#fff3e0',
                            border: '1px solid #ffb74d',
                            mb: 2,
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 1.5,
                        }}>
                            <WarningAmberIcon sx={{ color: '#f57c00', mt: 0.25 }} />
                            <Box>
                                <Typography variant="body2" fontWeight={700} color="#e65100">
                                    Account Temporarily Frozen
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    For your security, your account has been temporarily restricted.
                                    Contact support to restore access.
                                </Typography>
                            </Box>
                        </Box>
                    )}

                    {/* Case Information */}
                    {caseId && (
                        <Box sx={{
                            p: 2, borderRadius: 2,
                            bgcolor: '#f5f5f5',
                            mb: 2,
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <SecurityIcon sx={{ color: C.brown, fontSize: 20 }} />
                                <Typography variant="body2" fontWeight={700} color={C.brown}>
                                    Fraud Case Created
                                </Typography>
                            </Box>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Typography variant="caption" color="text.secondary">Case ID</Typography>
                                <Typography variant="caption" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
                                    {caseId}
                                </Typography>
                            </Box>
                            {typology && (
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                                    <Typography variant="caption" color="text.secondary">Typology</Typography>
                                    <Chip label={typology} size="small"
                                        sx={{ height: 18, fontSize: 10, fontWeight: 600 }} />
                                </Box>
                            )}
                        </Box>
                    )}

                    <Divider sx={{ my: 2 }} />

                    {/* Support Contact */}
                    <Box sx={{
                        p: 2, borderRadius: 2,
                        bgcolor: '#e3f2fd',
                        border: '1px solid #90caf9',
                        textAlign: 'center',
                    }}>
                        <SupportAgentIcon sx={{ color: '#1976d2', fontSize: 32, mb: 1 }} />
                        <Typography variant="body2" fontWeight={700} color="#1565c0">
                            Need Help?
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            Contact our 24/7 fraud support line
                        </Typography>
                        <Typography variant="h6" fontWeight={800} color="#1565c0" sx={{ mt: 1 }}>
                            1800-XXX-XXXX
                        </Typography>
                    </Box>

                    {/* Close Button */}
                    <Button
                        fullWidth
                        variant="contained"
                        onClick={onClose}
                        sx={{
                            mt: 2.5, py: 1.5, fontWeight: 700,
                            bgcolor: C.brown,
                            '&:hover': { bgcolor: C.brownMid },
                        }}
                    >
                        I Understand
                    </Button>
                </Box>
            </DialogContent>
        </Dialog>
    );
}
