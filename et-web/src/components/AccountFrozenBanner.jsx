import { Box, Typography, Button, Chip } from '@mui/material';
import BlockIcon from '@mui/icons-material/Block';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';

const C = {
    error: '#f44336',
    errorLight: '#ffebee',
    brown: '#7f5539',
};

/**
 * AccountFrozenBanner - Displays prominent banner when account is frozen
 *
 * Shows at the top of the dashboard when the customer's account
 * has been frozen due to suspected fraud.
 */
export default function AccountFrozenBanner({
    reason,
    frozenAt,
    alertId,
    onContactSupport,
}) {
    return (
        <Box sx={{
            mb: 3,
            p: 2.5,
            borderRadius: 2,
            background: 'linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%)',
            border: '2px solid #f4433650',
            animation: 'shake 0.5s ease-in-out',
            '@keyframes shake': {
                '0%, 100%': { transform: 'translateX(0)' },
                '10%, 30%, 50%, 70%, 90%': { transform: 'translateX(-2px)' },
                '20%, 40%, 60%, 80%': { transform: 'translateX(2px)' },
            },
        }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                <Box sx={{
                    width: 48, height: 48,
                    borderRadius: '50%',
                    bgcolor: C.error,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                }}>
                    <BlockIcon sx={{ color: 'white', fontSize: 28 }} />
                </Box>

                <Box sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <Typography variant="h6" fontWeight={800} color={C.error}>
                            Account Frozen
                        </Typography>
                        <Chip
                            label="Action Required"
                            size="small"
                            sx={{
                                bgcolor: C.error,
                                color: 'white',
                                fontWeight: 700,
                                fontSize: 10,
                                height: 20,
                                animation: 'pulse 2s infinite',
                                '@keyframes pulse': {
                                    '0%, 100%': { opacity: 1 },
                                    '50%': { opacity: 0.7 },
                                },
                            }}
                        />
                    </Box>

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                        Your account has been temporarily restricted due to suspicious activity.
                        All transactions are blocked until this is resolved.
                    </Typography>

                    {reason && (
                        <Box sx={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 0.5,
                            px: 1.5, py: 0.5,
                            borderRadius: 1,
                            bgcolor: 'rgba(244,67,54,0.1)',
                            mb: 1.5,
                        }}>
                            <Typography variant="caption" color="text.secondary">
                                Reason:
                            </Typography>
                            <Typography variant="caption" fontWeight={700} color={C.error}>
                                {reason}
                            </Typography>
                        </Box>
                    )}

                    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
                        <Button
                            variant="contained"
                            size="small"
                            startIcon={<SupportAgentIcon />}
                            onClick={onContactSupport}
                            sx={{
                                bgcolor: C.brown,
                                fontWeight: 700,
                                '&:hover': { bgcolor: '#5d4037' },
                            }}
                        >
                            Contact Support
                        </Button>
                        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
                            24/7 Helpline: 1800-XXX-XXXX
                        </Typography>
                    </Box>

                    {frozenAt && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                            Frozen since: {new Date(frozenAt).toLocaleString()}
                            {alertId && ` • Reference: ${alertId}`}
                        </Typography>
                    )}
                </Box>
            </Box>
        </Box>
    );
}
